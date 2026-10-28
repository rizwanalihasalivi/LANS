import boot10 as boot9
import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
from study10 import Env,FIELDS,P,logits,np

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot9.Path,required=True);a=p.parse_args();out=a.run;cfg=P['development'];rows=[];ticks=queries=exact=0
    for pair,seed in enumerate((701,802,903)):
        models={}
        for kind in ('student','causal_history'):
            with np.load(boot9.ROOT/f'docs/research/reviewer-pipeline-v9/actors/{kind}-{seed}.npz',allow_pickle=False) as z:models[kind]={k:z[k].copy() for k in z.files}
        rr=list(csv.DictReader((out/f'pair-{pair}/episodes.csv').open()))
        keys={(int(r['speed']),r['path'],int(r['mirror']),r['scenario'],r['source']) for r in rr}
        assert len(rr)==len(keys)==120 and keys==set(itertools.product(cfg['speeds'],cfg['paths'],cfg['mirrors'],cfg['scenarios'],cfg['sources']))
        for row in rr:
            with np.load(out/f'pair-{pair}/traces'/row['trace'],allow_pickle=False) as file:d={k:file[k].copy() for k in file.files}
            source=row['source'];scenario=row['scenario'];speed=int(row['speed']);sign=int(row['mirror']);case=(speed,row['path'],sign,'tire' if scenario=='tire' else 'nominal',int(row['noise_id']))
            env=Env(case=case,source=source,scenario=scenario);env.reset();raw=[];replayed={k:[] for k in FIELDS};reasons=[];qq=[];hh=[];n=len(d['command'])
            mask=d['submitted'].astype(bool);model=models.get('causal_history' if source.startswith('ppo_') else source.split('_')[0])
            if model is not None:
                xx=d['query'][mask];assert np.isfinite(xx).all() and np.all(xx[:,[16,17]]==0)
                residual=np.array([-.08,-.04,0,.04,.08])[[int(logits(model,x[None,:]).argmax(1)[0]) for x in xx]]
                np.testing.assert_allclose(residual,d['proposed_residual'][mask],rtol=0,atol=1e-12);queries+=len(xx)
            for i in range(n):
                if source=='planner_rk' and env.ctrl.pending is None:
                    from planner10 import propose
                    expected=propose(env.ctrl,env.estimate,env.state[5],env.measured_speed,env.ctrl.previews,env.gain,env.gains,env.tick*.01)
                    assert expected==float(d['proposed_residual'][i])
                raw.append(env.raw.copy());query=np.full(20,np.nan,np.float32);meta=None
                if env.ctrl.pending is None:
                    query=env.obs.copy()
                    meta=env.query_meta
                qq.append(query);hh.append([meta[k] for k in ('estimated_delay_s','used_horizon_s','completed_history_samples','last_completed_sequence')] if meta else [0,0,0,-1])
                _,_,_,_,checked=env.step_residual(float(d['proposed_residual'][i]));reasons.append(checked['reason'])
                for key in FIELDS:replayed[key].append(math.nan if checked[key] is None else checked[key])
            np.testing.assert_array_equal(np.array(raw),d['raw']);np.testing.assert_array_equal(np.array(qq),d['query']);np.testing.assert_array_equal(np.array(hh),d['forecast_history'])
            np.testing.assert_array_equal(np.array(reasons),d['reason'])
            for key in FIELDS:np.testing.assert_allclose(replayed[key],d[key],rtol=0,atol=1e-11,equal_nan=True)
            assert np.max(np.abs(d['command']))<=.5000001 and np.max(np.abs(d['steering_rate']))<=.3500001
            assert np.all((d['packet_age_s'][d['weight']>0]>=0)&(d['packet_age_s'][d['weight']>0]<.05))
            h=int(row['scheduled']);values=dict(rmse_m=math.sqrt((float(d['lateral_error']@d['lateral_error'])+(h-n)*6.25)/h),heading_rmse_rad=math.sqrt(float(d['heading_error']@d['heading_error'])/n),rate_rms_rad_s=math.sqrt(float(d['steering_rate']@d['steering_rate'])/n))
            for k,v in values.items():assert abs(v-float(row[k]))<1e-12
            assert int(row['active_ticks'])==np.count_nonzero(d['weight']>0)
            if scenario=='delay100' and source!='lqr':
                baseline=out/f'pair-{pair}/traces'/row['trace'].replace('-'+source+'.npz','-lqr.npz')
                with np.load(baseline,allow_pickle=False) as b:
                    for key in ('command','x','y','heading','actuator'):np.testing.assert_array_equal(d[key],b[key])
                exact+=1
            ticks+=n
        rows+=rr;print(pair,len(rows),ticks,queries,flush=True)
    mean=lambda rr,k:statistics.mean(float(r[k]) for r in rr)
    summary={}
    for source in cfg['sources']:
        rr=[r for r in rows if r['source']==source];m={k:mean(rr,k) for k in ('rmse_m','heading_rmse_rad','rate_rms_rad_s','movement_rad')}
        m.update(episodes=len(rr),survived=sum(r['survived']=='True' for r in rr),active_ticks=sum(int(r['active_ticks']) for r in rr));summary[source]=m
    base=summary['lqr']
    for m in summary.values():m['gain_vs_lqr_pct']=100*(1-m['rmse_m']/base['rmse_m'])
    target_gains={ref:100*(1-summary['ppo_rk']['rmse_m']/summary[ref]['rmse_m']) for ref in ('lqr','student_rk','planner_rk','ppo_euler')}
    balanced=lambda source: all(summary[source][k]<=1.05*base[k] for k in ('heading_rmse_rad','rate_rms_rad_s')) and summary[source]['survived']==summary[source]['episodes']
    headroom=all(summary['planner_rk']['rmse_m']<=.8*summary[ref]['rmse_m'] for ref in ('lqr','student_rk')) and balanced('planner_rk')
    for name,digest in json.loads((out/'manifest.json').read_text())['hashes'].items():assert hashlib.sha256((boot9.ROOT/name).read_bytes()).hexdigest()==digest,name
    decision=dict(episodes=len(rows),transitions=ticks,submitted_actor_decisions=queries,full_causal_query_gate_physical_replay=True,source_model_hashes_verified=True,ppo_gain_vs_comparators_pct=target_gains,diagnostic_twenty_percent_pass=all(v>=20 for v in target_gains.values()) and balanced('ppo_rk'),causal_planner_20pct_balanced_headroom=headroom,new_training_steps=0,full_promotion=False,reserved='unopened; diagnostic is not full selection or timing confirmation',scope='Known paths, nominal/tire/20ms logical delivery only; other baselines and latencies absent')
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    print(json.dumps(decision,indent=2))
if __name__=='__main__':main()
