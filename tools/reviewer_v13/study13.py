"""Predeclared paired matrix, one atomic raw trace and record per episode."""
import boot13
import itertools
import json
import math
import os
import uuid
import numpy as np
from env13 import Env
from models13 import residual
from checkpoint12 import atomic_json,digest

P=json.loads((boot13.HERE/'protocol.json').read_text())


def split(method):
    return ('lqr','none') if method=='lqr' else tuple(method.split('_',1))


def make_env(case,method,scenario):
    return Env(profile=split(method)[0],case=case,scenario=scenario)


def action(env,method,model):
    if env.ctrl.pending is not None:return 0.
    source=split(method)[1]
    if source=='negative':return -.04
    if source=='positive':return .04
    return residual(model,env.obs) if model is not None else 0.


def metrics(data,horizon):
    n=len(data['command']);failed=bool(data['failed'][-1])
    return dict(steps=n,scheduled=horizon,survived=not failed,
        rmse_m=math.sqrt((sum(data['lateral_error']**2)+(horizon-n)*6.25)/horizon),
        heading_rmse_rad=math.sqrt(sum(data['heading_error']**2)/n),rate_rms_rad_s=math.sqrt(sum(data['steering_rate']**2)/n),
        movement_rad=float(sum(abs(data['steering_rate']))*.01),active_ticks=int(sum(abs(data['command']-data['baseline'])>1e-10)),
        saturated_ticks=int(sum(abs(data['steering_rate'])>.349)),projected_ticks=int(sum(data['projection']<1.-1e-10)))


def episode(case,method,scenario,model,path):
    env=make_env(case,method,scenario);env.reset();rows=[]
    while True:
        proposal=action(env,method,model)
        _,_,failed,done,row=env.step_residual(proposal);rows.append(row)
        if failed or done:break
    data={k:np.array([math.nan if r[k] is None else r[k] for r in rows]) for k in rows[0]}
    temp=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
    with temp.open('wb') as f:np.savez_compressed(f,**data);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    return dict(**metrics(data,env.horizon),trace_sha256=digest(path))


def models_for(out,pair):
    result={}
    for source in ('ppo','student','legacy','physical'):
        with np.load(out/f'actors/{source}-{pair}.npz',allow_pickle=False) as f:result[source]={k:f[k].copy() for k in f.files}
    return result


def cases(pair):
    cfg=P['development']
    for speed,path,sign,scenario in itertools.product(cfg['speeds'],cfg['paths'],cfg['mirrors'],cfg['scenarios']):
        noise=cfg['noise_base']+pair*100000+speed*1000+cfg['paths'].index(path)*100+cfg['scenarios'].index(scenario)*10
        yield (speed,path,sign,'nominal' if scenario=='poll10' else scenario,noise),scenario


def main(out,pair):
    folder=out/f'pair-{pair}/traces';folder.mkdir(parents=True,exist_ok=True)
    models=models_for(out,pair);count=0
    for case,scenario in cases(pair):
        speed,path,sign,_,noise=case
        for method in P['development']['methods']:
            name=f'{speed}-{path}-{sign}-{scenario}-{method}';trace=folder/(name+'.npz');record=folder/(name+'.json')
            if record.exists():
                row=json.loads(record.read_text());assert row['trace_sha256']==digest(trace),name
            else:
                m=episode(case,method,scenario,models.get(split(method)[1]),trace)
                row=dict(pair=pair,speed=speed,path=path,mirror=sign,scenario=scenario,method=method,noise_id=noise,trace=trace.name,**m)
                atomic_json(record,row)
            count+=1
        print(pair,speed,path,sign,scenario,count,flush=True)
    atomic_json(out/f'pair-{pair}/complete.json',dict(episodes=count))


if __name__=='__main__':
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--pair',type=int,required=True);a=p.parse_args();main(a.out,a.pair)
