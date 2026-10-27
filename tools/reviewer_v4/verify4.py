import boot4
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
from interface4 import P,AsyncEnv,planner


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot4.Path,required=True);args=p.parse_args();out=args.run
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    allrows=[];queries={};exact=0;transitions=0;grid=P['development']
    for pair in range(3):
        models={'student':load_causal(boot4.ROOT/f'docs/research/causal-interface-2026-10-26/models/{P["development"]["student_seeds"][pair]}'),
            
            'ppo':PPO.load(boot4.ROOT/f'docs/research/reviewer-aligned-v3/training-{pair}/policy.zip',device='cpu')}
        models['oldage_ppo']=models['ppo']
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
                assert all(float(r[f'obs{i}'])==0 for i in (14,15,16,17,19))
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
                with torch.no_grad():index=models[source](torch.from_numpy(x)).argmax(1).numpy() if source=='student' else models[source].predict(x,deterministic=True)[0]
                assert np.allclose(np.array([-.08,-.04,0.,.04,.08])[index],[float(r['proposed_residual']) for r in submitted],rtol=0,atol=1e-8)
                queries[source]=queries.get(source,0)+len(x)
            replay=AsyncEnv((int(row['speed']),row['path'],int(row['mirror']),row['scenario'],int(row['noise_id'])),source)
            replay.reset()
            for r in rr:
                np.testing.assert_array_equal(replay.obs,np.array([float(r[f'obs{i}']) for i in range(20)],np.float32))
                assert abs(float(r['service_s'])-replay.service)<1e-12
                if source=='planner' and r['submitted']=='True':assert abs(planner(replay)-float(r['proposed_residual']))<1e-12
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
    c=metrics['ppo'];reasons=[]
    for reference in ('lqr','student','negative','positive'):
        if c['rmse_m']>.99*metrics[reference]['rmse_m']:reasons.append('lacks1% gain vs '+reference)
        if c['survived']<metrics[reference]['survived']:reasons.append('survival vs '+reference)
    for name in ('heading_rmse_rad','rate_rms_rad_s'):
        if c[name]>1.05*base[name]:reasons.append(name+' >1.05LQR')
    seedgains=[]
    for pair in range(3):
        a=[r for r in allrows if int(r['pair'])==pair and r['source']=='ppo'];b=[r for r in allrows if int(r['pair'])==pair and r['source']=='student']
        gain=100*(1-mean(a,'rmse_m')/mean(b,'rmse_m'));seedgains.append(gain)
        if gain<=0:reasons.append(f'pair{pair} no student gain')
    a=[r for r in allrows if r['source']=='ppo' and r['scenario']=='nominal'];b=[r for r in allrows if r['source']=='lqr' and r['scenario']=='nominal']
    if mean(a,'rmse_m')>1.02*mean(b,'rmse_m'):reasons.append('nominal >2% worse than LQR')
    manifest=json.loads((out/'manifest.json').read_text())
    for name,digest in manifest['hashes'].items():assert hashlib.sha256((boot4.ROOT/name).read_bytes()).hexdigest()==digest,name
    decision=dict(eligible=not reasons,reasons=reasons,paired_seed_gains_vs_student_pct=seedgains,episodes=len(allrows),
        transitions=transitions,submitted_queries_replayed=queries,severe_exact_pairs=exact,
        raw_metrics_filter_fusion_reward_model_hashes_verified=True,reserved='unopened; corresponding selected-controller timing required separately')
    pc=metrics['planner'];pr=[];pg=[]
    for ref in ('lqr','student','negative','positive'):
        if pc['rmse_m']>.99*metrics[ref]['rmse_m']:pr.append('lacks1% gain vs '+ref)
        if pc['survived']<metrics[ref]['survived']:pr.append('survival vs '+ref)
    for name in ('heading_rmse_rad','rate_rms_rad_s'):
        if pc[name]>1.05*base[name]:pr.append(name+' >1.05LQR')
    for pair in range(3):
        aa=[r for r in allrows if int(r['pair'])==pair and r['source']=='planner'];bb=[r for r in allrows if int(r['pair'])==pair and r['source']=='student']
        gain=100*(1-mean(aa,'rmse_m')/mean(bb,'rmse_m'));pg.append(gain)
        if gain<=0:pr.append(f'pair{pair} no student gain')
    aa=[r for r in allrows if r['source']=='planner' and r['scenario']=='nominal']
    if mean(aa,'rmse_m')>1.02*mean(b,'rmse_m'):pr.append('nominal >2% worse than LQR')
    decision.update(planner_headroom_screen_pass=not pr,planner_headroom_reasons=pr,planner_group_gains_vs_student_pct=pg,
        full_observer_plant_query_replay_verified=True,planner_current_observable_state_replay_verified=True)
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
    with (out/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=allrows[0],lineterminator='\n');w.writeheader();w.writerows(allrows)
    lines=['# Freshness-interface and scalar-predictor development study','',
        '27 October2026. Frozen single freshness variant; no training; old evidence unchanged. No post-outcome tuning or reserved evaluation.','',
        '| Source | Tracking gain vs LQR | Heading change | Actuator-rate change | Survival |', '|---|---:|---:|---:|---:|']
    for source,m in metrics.items():lines.append(f'| {source} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.2f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.2f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['',f'Eligible: {not reasons}. Reasons: '+('; '.join(reasons) or 'all frozen development gates passed'),'',
        'The same frozen v3 PPO endpoints and original students are used without training. oldage_ppo retains the legacy steep age-gain; other proposal methods share the new freshness-only authority. All cases enforce minimum10ms simulated delivery. Planner is a causal finite nominal nonlearned reference, not an optimal-policy or safety proof. All rewards/actuator/observer limits are unchanged.', '',
        'Three training/noise pairs are small-sample development evidence; control ticks are not independent experiments. Physical readiness and hard real-time execution require separate evidence. No failed test is relabeled as a pass.']
    (out/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps(decision,indent=2))


if __name__=='__main__':main()
