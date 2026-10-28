"""Matched full development matrix; typed traces avoid lossy CSV parsing."""
import boot10 as boot9
import argparse
import csv
import itertools
import json
import math
import sys
sys.path.insert(0,str(boot9.ROOT/'tools/reviewer_v5'))
from history5 import HistoryEnv
from supervisor import observation
from recovery8 import RecoveryController
import numpy as np

P=json.loads((boot9.HERE/'protocol.json').read_text())
FIELDS=('command','baseline','weight','filtered_residual','x','y','heading','actuator','lateral_error','heading_error','steering_rate','reward','proposed_residual','packet_seq','packet_age_s','submitted','failed','predicted_base','predicted_candidate')

def logits(model,x):
    z=(np.asarray(x,np.float32)-model['mean'])/model['std']
    return np.tanh(np.tanh(z@model['w0']+model['b0'])@model['w1']+model['b1'])@model['w2']+model['b2']

from env10 import Env
from planner10 import propose
import time

def episode(case,source,scenario,model,path):
    env=Env(case=case,source=source,scenario=scenario);obs,_=env.reset();rows=[];raw=[];queries=[];reasons=[];history=[];planner_ns=[]
    while True:
        query=np.full(20,np.nan,np.float32);res=0.;meta=None
        if env.ctrl.pending is None:
            query=obs.copy()
            meta=env.query_meta
            if source=='negative':res=-.04
            elif source=='positive':res=.04
            elif source=='planner_rk':
                start=time.perf_counter_ns();res=propose(env.ctrl,env.estimate,env.state[5],env.measured_speed,env.ctrl.previews,env.gain,env.gains,env.tick*.01);planner_ns.append(time.perf_counter_ns()-start)
            elif model is not None:res=[-.08,-.04,0.,.04,.08][int(logits(model,query[None,:]).argmax(1)[0])]
        raw.append(env.raw.copy());queries.append(query)
        history.append([meta[k] for k in ('estimated_delay_s','used_horizon_s','completed_history_samples','last_completed_sequence')] if meta is not None else [0,0,0,-1])
        obs,_,failed,done,row=env.step_residual(res);rows.append(row);reasons.append(row['reason'])
        if failed or done:break
    data={k:np.array([math.nan if r[k] is None else r[k] for r in rows]) for k in FIELDS}
    data.update(planner_ns=np.array(planner_ns,dtype=np.int64),raw=np.array(raw),query=np.array(queries),forecast_history=np.array(history),reason=np.array(reasons))
    np.savez_compressed(path,**data)
    n=len(rows);h=env.horizon
    return dict(steps=n,scheduled=h,survived=not failed,rmse_m=math.sqrt((sum(r['lateral_error']**2 for r in rows)+(h-n)*6.25)/h),
        heading_rmse_rad=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),rate_rms_rad_s=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),
        active_ticks=sum(r['weight']>0 for r in rows),movement_rad=sum(abs(r['steering_rate'])*.01 for r in rows))

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot9.Path,required=True);p.add_argument('--pair',type=int,choices=range(3),required=True);a=p.parse_args();out=a.run/f'pair-{a.pair}';out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir()
    models={}
    for kind in ('student','causal_history'):
        with np.load(boot9.ROOT/f'docs/research/reviewer-pipeline-v9/actors/{kind}-{(701,802,903)[a.pair]}.npz',allow_pickle=False) as z:models[kind]={k:z[k].copy() for k in z.files}
    cfg=P['development'];count=0
    with (out/'episodes.csv').open('w',newline='') as stream:
        writer=None
        for speed,path,sign,scenario in itertools.product(cfg['speeds'],cfg['paths'],cfg['mirrors'],cfg['scenarios']):
            noise=cfg['noise_base']+a.pair*100000+speed*1000+cfg['paths'].index(path)*100+cfg['scenarios'].index(scenario)*10
            case=(speed,path,sign,'tire' if scenario=='tire' else 'nominal',noise)
            for source in cfg['sources']:
                name=f'{speed}-{path}-{sign}-{scenario}-{source}.npz';model=models.get('causal_history' if source.startswith('ppo_') else source.split('_')[0])
                m=episode(case,source,scenario,model,out/'traces'/name)
                row=dict(pair=a.pair,speed=speed,path=path,mirror=sign,scenario=scenario,source=source,noise_id=noise,trace=name,**m)
                if writer is None:writer=csv.DictWriter(stream,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);stream.flush();count+=1
            print(a.pair,speed,path,sign,scenario,count,flush=True)
    (out/'complete.json').write_text(json.dumps(dict(episodes=count))+'\n')

if __name__=='__main__':main()
