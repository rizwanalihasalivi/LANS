"""Raw metric recomputation, Torch actor checks, full dynamics/controller replay."""
import boot13
import csv
import json
import math
import statistics
import numpy as np
import torch
from stable_baselines3 import PPO
from checkpoint12 import atomic_json,digest
from models13 import original,VALUES
from study13 import P,cases,models_for,split,make_env,action


def equal(expected,actual,key):
    if isinstance(expected,(bool,np.bool_,str,np.str_,int,np.integer)):
        assert expected==actual,(key,expected,actual)
    elif math.isnan(float(expected)):
        assert actual is None or math.isnan(float(actual)),(key,expected,actual)
    else:assert math.isclose(float(expected),float(actual),abs_tol=1e-11,rel_tol=0),(key,expected,actual)


def torch_model(out,pair,source):
    if source in ('ppo','student'):return original(pair,source)
    pointer=json.loads((out/f'{source}-{pair}/checkpoints/latest.json').read_text())
    with (out/f'{source}-{pair}/checkpoints'/pointer['folder']/'model.zip').open('rb') as f:return PPO.load(f,device='cpu')


def torch_actions(model,obs,source):
    obs=obs.copy()
    if source in ('ppo','student'):obs[:,14]=0.
    with torch.no_grad():
        x=torch.as_tensor(obs,dtype=torch.float32)
        if source=='student':scores=model.net((x-model.mean)/model.std)
        else:scores=model.policy.get_distribution(x).distribution.logits
        return VALUES[scores.argmax(1).numpy()]


def independent_metrics(data,horizon):
    n=len(data['command'])
    rms=lambda key:math.sqrt(math.fsum(float(x)**2 for x in data[key])/n)
    return dict(steps=n,scheduled=horizon,survived=not bool(data['failed'][-1]),
        rmse_m=math.sqrt((math.fsum(float(x)**2 for x in data['lateral_error'])+(horizon-n)*6.25)/horizon),
        heading_rmse_rad=rms('heading_error'),rate_rms_rad_s=rms('steering_rate'),
        movement_rad=math.fsum(abs(float(x)) for x in data['steering_rate'])*.01,
        active_ticks=sum(abs(float(a)-float(b))>1e-10 for a,b in zip(data['command'],data['baseline'])),
        saturated_ticks=sum(abs(float(x))>.349 for x in data['steering_rate']),
        projected_ticks=sum(float(x)<1.-1e-10 for x in data['projection']))


def main(out):
    torch.set_num_threads(1);records=[];transitions=queries=exact_fallback=0
    for pair in range(3):
        models=models_for(out,pair);tm={s:torch_model(out,pair,s) for s in models}
        for case,scenario in cases(pair):
            speed,path,sign,_,noise=case;baseline=None
            for method in P['development']['methods']:
                name=f'{speed}-{path}-{sign}-{scenario}-{method}';folder=out/f'pair-{pair}/traces'
                record=json.loads((folder/(name+'.json')).read_text());trace=folder/(name+'.npz')
                assert record['trace_sha256']==digest(trace)
                with np.load(trace,allow_pickle=False) as f:data={k:f[k] for k in f.files}
                env=make_env(case,method,scenario);env.reset();source=split(method)[1]
                for key,value in independent_metrics(data,env.horizon).items():equal(record[key],value,key)
                if source in tm:
                    select=np.asarray(data['submitted'],bool)
                    x=np.stack([data[f'obs{j}'][select] for j in range(20)],axis=1).astype(np.float32)
                    actions=torch_actions(tm[source],x,source);recorded=data['proposed_residual'][select]
                    # Batched GEMM can differ near an argmax tie. Production
                    # uses one row; recheck every disagreement at that shape.
                    for i in np.flatnonzero(actions!=recorded):
                        assert torch_actions(tm[source],x[i:i+1],source)[0]==recorded[i],(name,'actor',i)
                    queries+=len(x)
                for i in range(record['steps']):
                    proposal=action(env,method,models.get(source))
                    _,_,failed,done,row=env.step_residual(proposal)
                    for key in data:equal(data[key][i],row[key],(name,i,key))
                    if i+1<record['steps']:assert not (failed or done)
                assert failed or done
                if method=='lqr':baseline={k:data[k].copy() for k in ('command','actuator','lateral_error','heading_error')}
                elif scenario=='delay100':
                    assert np.all(data['weight']==0)
                    for k,v in baseline.items():np.testing.assert_array_equal(data[k],v)
                    exact_fallback+=1
                if method.startswith('budget'):
                    mask=np.isfinite(data['candidate_rate_prediction'])
                    assert np.all(data['candidate_rate_prediction'][mask]<=np.minimum(.35,1.02*data['baseline_rate_prediction'][mask])+1e-10)
                records.append(record);transitions+=record['steps']
        print('replayed',pair,len(records),transitions,queries,flush=True)
    assert len(records)==P['development']['episodes']
    with (out/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
    def aggregate(group):
        return {method:dict(episodes=len(g),survived=sum(r['survived'] for r in g),
                    **{k:statistics.mean(r[k] for r in g) for k in ('rmse_m','heading_rmse_rad','rate_rms_rad_s','movement_rad')},
                    active_fraction=sum(r['active_ticks'] for r in g)/sum(r['steps'] for r in g),
                    saturation_fraction=sum(r['saturated_ticks'] for r in g)/sum(r['steps'] for r in g))
                for method in P['development']['methods'] if (g:=[r for r in group if r['method']==method])}
    overall=aggregate(records);by_scenario={s:aggregate([r for r in records if r['scenario']==s]) for s in P['development']['scenarios']}
    by_pair={str(p):aggregate([r for r in records if r['pair']==p]) for p in range(3)}
    by_speed={str(v):aggregate([r for r in records if r['speed']==v]) for v in P['development']['speeds']}
    b=overall['lqr'];summary={}
    for method,m in overall.items():
        summary[method]=dict(**m,gain_vs_lqr_pct=100*(1-m['rmse_m']/b['rmse_m']),
            heading_change_pct=100*(m['heading_rmse_rad']/b['heading_rmse_rad']-1),rate_change_pct=100*(m['rate_rms_rad_s']/b['rate_rms_rad_s']-1))
    decisions={};a=P['acceptance']
    for method in ('budget_ppo','budget_legacy','budget_physical'):
        m=overall[method];gains={other:100*(1-m['rmse_m']/overall[other]['rmse_m']) for other in a['comparators']}
        nominal_pairs=[aggregate([r for r in records if r['pair']==p and r['scenario']=='nominal']) for p in range(3)]
        checks=dict(tracking=all(v>=a['tracking_gain_min_pct'] for v in gains.values()),
            heading=m['heading_rmse_rad']<=a['heading_ratio_max']*b['heading_rmse_rad'],
            rate=m['rate_rms_rad_s']<=a['rate_ratio_max']*b['rate_rms_rad_s'],survival=m['survived']==m['episodes'],
            nominal=all(q[method]['rmse_m']<=a['nominal_tracking_ratio_max']*q['lqr']['rmse_m'] for q in nominal_pairs),
            paired_student=all(q[method]['rmse_m']<q['budget_student']['rmse_m'] for q in by_pair.values()),exact_100ms_fallback=True)
        decisions[method]=dict(gains_pct=gains,checks=checks,full_screen_pass=all(checks.values()),twenty_percent_pass=all(checks.values()) and all(v>=20 for v in gains.values()))
    atomic_json(out/'summary.json',dict(overall=summary,by_scenario=by_scenario,by_pair=by_pair,by_speed=by_speed))
    atomic_json(out/'verification.json',dict(episodes=len(records),transitions=transitions,neural_queries=queries,exact_fallback_pairs=exact_fallback,full_replay=True,independent_metric_recomputation=True,torch_actor_checks=True))
    atomic_json(out/'decision.json',decisions);print(json.dumps(decisions,indent=2),flush=True)


if __name__=='__main__':
    from pathlib import Path
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
