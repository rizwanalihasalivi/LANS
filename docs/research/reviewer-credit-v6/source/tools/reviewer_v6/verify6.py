import boot6
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import statistics
import numpy as np
import torch
from stable_baselines3 import PPO
from causal_student import load_causal
from history5 import HistoryEnv,Bridge
P=json.loads((boot6.HERE/"protocol.json").read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot6.Path,required=True);args=p.parse_args();out=args.run
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    allrows=[];queries={};exact=0;transitions=0;grid=P['development']
    for pair in range(3):
        models={'student':Bridge('student',pair),'v3ppo':Bridge('ppo',pair)}
        for arm in P['arms']:models[arm]=PPO.load(out/f'{arm}-{pair}/policy.zip',device='cpu')
        assert all(torch.count_nonzero(models[arm].policy.mlp_extractor.policy_net[0].weight[:,14])==0 for arm in P['arms'])
        batch=list(csv.DictReader((out/f'pair-{pair}/episodes.csv').open()))
        expected=set(itertools.product(grid['speeds'],grid['paths'],grid['mirrors'],grid['scenarios'],grid['sources']))
        keys=[(int(r['speed']),r['path'],int(r['mirror']),r['scenario'],r['source']) for r in batch]
        assert len(keys)==len(set(keys))==len(expected) and set(keys)==expected
        def read(key):
            with gzip.open(out/f'pair-{pair}/traces'/('-'.join(map(str,key))+'.csv.gz'),'rt') as f:return list(csv.DictReader(f))
        for row,key in zip(batch,keys):
            rr=read(key);n=len(rr);h=int(row['scheduled']);source=row['source']
            lateral=math.sqrt((sum(float(r['lateral_error'])**2 for r in rr)+(h-n)*6.25)/h)
            heading=math.sqrt(sum(float(r['heading_error'])**2 for r in rr)/n);rate=math.sqrt(sum(float(r['steering_rate'])**2 for r in rr)/n)
            for actual,name in ((lateral,'rmse_m'),(heading,'heading_rmse_rad'),(rate,'rate_rms_rad_s')):assert abs(actual-float(row[name]))<1e-12
            previous=0.
            for r in rr:
                command,baseline,weight,filtered=map(float,(r['command'],r['baseline'],r['weight'],r['filtered_residual']))
                assert abs(command)<=.5000001 and abs(float(r['steering_rate']))<=.3500001
                assert all(float(r[f'obs{i}'])==0 for i in (15,16,17,19))
                if source!='lqr':
                    if r['reason'] in ('missing','age','sequence','nonfinite','envelope','prediction_invalid'):assert filtered==0 and weight==0
                    else:assert abs(filtered-(previous+(1-math.exp(-.01/.3))*(float(r['packet_residual'])-previous)))<1e-12
                    previous=filtered
                assert abs(command-max(-.5,min(.5,baseline+weight*filtered)))<1e-12
                if weight:
                    assert r['reason']=='accepted' and 0<=float(r['packet_age_s'])<.05
                    j0,j1=float(r['predicted_base']),float(r['predicted_candidate']);assert j0-j1>=max(1e-7,.001*j0)-1e-12
                reward=-(float(r['lateral_error'])/.5)**2-.2*(float(r['heading_error'])/.1)**2-.2*(float(r['steering_rate'])/.35)**2-.005*(command/.5)**2-10*(r['failed']=='True')
                assert abs(reward-float(r['reward']))<1e-12
            if source in models:
                submitted=[r for r in rr if r['submitted']=='True']
                x=np.array([[float(r[f'obs{i}']) for i in range(20)] for r in submitted],np.float32)
                with torch.no_grad():index=models[source](torch.from_numpy(x)).argmax(1).numpy() if isinstance(models[source],torch.nn.Module) else models[source].predict(x,deterministic=True)[0]
                assert np.allclose(np.array([-.08,-.04,0.,.04,.08])[index],[float(r['proposed_residual']) for r in submitted],rtol=0,atol=1e-8)
                queries[source]=queries.get(source,0)+len(x)
            replay=HistoryEnv(case=(int(row['speed']),row['path'],int(row['mirror']),row['scenario'],int(row['noise_id'])),source=source,history=True)
            replay.reset()
            for r in rr:
                np.testing.assert_array_equal(replay.obs,np.array([float(r[f'obs{i}']) for i in range(20)],np.float32))
                assert abs(float(r['service_s'])-replay.service)<1e-12
                _,_,_,_,checked=replay.step_residual(float(r['proposed_residual']))
                for field in ('command','baseline','weight','filtered_residual','x','y','heading','actuator','reward'):
                    assert abs(checked[field]-float(r[field]))<1e-11,(key,r['tick'],field)
                assert checked['reason']==r['reason']
            if row['scenario']=='delay100' and source!='lqr':
                baseline_rows=read(key[:4]+('lqr',));assert len(baseline_rows)==n
                assert all(all(a[k]==b[k] for k in ('command','x','y','heading','actuator')) for a,b in zip(rr,baseline_rows));exact+=1
            transitions+=n
        allrows+=batch;print(pair,len(allrows),queries,flush=True)
    mean=lambda rows,name:statistics.mean(float(r[name]) for r in rows)
    metrics={}
    for source in grid['sources']:
        rr=[r for r in allrows if r['source']==source]
        metrics[source]={name:mean(rr,name) for name in ('rmse_m','heading_rmse_rad','rate_rms_rad_s','movement_rad')}
        metrics[source].update(survived=sum(r['survived']=='True' for r in rr),episodes=len(rr),active=sum(int(r['active']) for r in rr))
    base=metrics['lqr']
    for m in metrics.values():m['gain_vs_lqr_pct']=100*(1-m['rmse_m']/base['rmse_m'])
    screens={};eligible=[]
    for arm in P['arms']:
        c=metrics[arm];reasons=[];gains=[]
        for ref in ('lqr','student','negative','positive'):
            if c['rmse_m']>.99*metrics[ref]['rmse_m']:reasons.append('lacks1% gain vs '+ref)
            if c['survived']<metrics[ref]['survived']:reasons.append('survival vs '+ref)
        for key in ('heading_rmse_rad','rate_rms_rad_s'):
            if c[key]>1.05*base[key]:reasons.append(key+' >1.05LQR')
        for pair in range(3):
            aa=[r for r in allrows if int(r['pair'])==pair and r['source']==arm];bb=[r for r in allrows if int(r['pair'])==pair and r['source']=='student']
            gain=100*(1-mean(aa,'rmse_m')/mean(bb,'rmse_m'));gains.append(gain)
            if gain<=0:reasons.append(f'pair{pair} no student gain')
            meta=json.loads((out/f'{arm}-{pair}/complete.json').read_text())
            if not meta['endpoint_eligible']:reasons.append(f'pair{pair} endpoint ineligible')
            if arm in P['arms']:assert torch.count_nonzero(models[arm].policy.mlp_extractor.policy_net[0].weight[:,14])==0
        aa=[r for r in allrows if r['source']==arm and r['scenario']=='nominal'];bb=[r for r in allrows if r['source']=='lqr' and r['scenario']=='nominal']
        if mean(aa,'rmse_m')>1.02*mean(bb,'rmse_m'):reasons.append('nominal >2% worse than LQR')
        screens[arm]=dict(eligible=not reasons,reasons=reasons,paired_group_gains_vs_student_pct=gains)
        if not reasons:eligible.append(arm)
    selected=min(eligible,key=lambda arm:(metrics[arm]['rmse_m'],P['arms'].index(arm))) if eligible else None
    manifest=json.loads((out/'manifest.json').read_text())
    for name,digest in manifest['hashes'].items():assert hashlib.sha256((boot6.ROOT/name).read_bytes()).hexdigest()==digest,name
    decision=dict(selected=selected,screens=screens,episodes=len(allrows),transitions=transitions,submitted_queries_replayed=queries,
        severe_exact_pairs=exact,full_observer_plant_query_and_causal_history_replay=True,source_and_model_hashes_verified=True,
        reserved='unopened; selected corresponding-model timing must pass separately')
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
    with (out/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=allrows[0],lineterminator='\n');w.writeheader();w.writerows(allrows)
    lines=['# Submitted-action credit training study','',
        '| Source | Tracking gain vs LQR | Heading change | Rate RMS change | Survival |','|---|---:|---:|---:|---:|']
    for name,m in metrics.items():lines.append(f'| {name} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.2f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.2f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['',f'Selected arm: {selected}.','',
        'New interface causal_filter_history_v5 explicitly assigns14 to past filtered residual/0.08;15/16/17/19 remainzero. All original models are logit-preserving bridges with input14ignored. Same fixed supervisor, objective and extra training budget in both credit arms; actor losses differ only by submitted-action masking. Existing v3 training/pretraining are extra; no per-seed checkpoint/arm selection. Finite development success is not unseen or physical validation.']
    (out/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps(decision,indent=2))


if __name__=='__main__':main()
