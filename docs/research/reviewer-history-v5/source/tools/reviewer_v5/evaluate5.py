import boot5
import argparse
import csv
import gzip
import itertools
import json
import math
import time
import torch
from stable_baselines3 import PPO
from causal_student import load_causal
from history5 import HistoryEnv,Bridge,P


def episode(source,model,case,path):
    env=HistoryEnv(case=case,source=source,history=True);obs,_=env.reset();rows=[]
    while True:
        start=time.perf_counter_ns();res=0.;inference=0
        if env.ctrl.pending is None:
            began=time.perf_counter_ns()
            if source=='negative':res=-.04
            elif source=='positive':res=.04
            elif model is not None:
                action,_=model.predict(obs,deterministic=True)
                res=[-.08,-.04,0.,.04,.08][int(action)]
            inference=time.perf_counter_ns()-began
        obs,_,failed,done,row=env.step_residual(res)
        row.update(inference_ns=inference,processing_ns=time.perf_counter_ns()-start,service_s=env.service);rows.append(row)
        if failed or done:break
    with gzip.open(path,'wt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    n=len(rows);h=env.horizon
    return dict(steps=n,scheduled=h,survived=not failed,rmse_m=math.sqrt((sum(r['lateral_error']**2 for r in rows)+(h-n)*6.25)/h),
        heading_rmse_rad=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),rate_rms_rad_s=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),
        movement_rad=sum(abs(r['steering_rate'])*.01 for r in rows),active=sum(r['weight']>0 for r in rows))


def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,required=True,choices=range(3));p.add_argument('--run',type=boot5.Path,required=True)
    args=p.parse_args();pair=args.pair;out=args.run/f'pair-{pair}';out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    models={'student':Bridge('student',pair),'v3ppo':Bridge('ppo',pair)}
    for arm in P['arms']:models[arm]=PPO.load(args.run/f'{arm}-{pair}/policy.zip',device='cpu')
    grid=P['development'];rows=[]
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=None
        for speed,path,sign,scenario in itertools.product(grid['speeds'],grid['paths'],grid['mirrors'],grid['scenarios']):
            noise=grid['noise_base']+pair*100000+speed*1000+grid['paths'].index(path)*100+grid['scenarios'].index(scenario)*10
            for source in grid['sources']:
                name=f'{speed}-{path}-{sign}-{scenario}-{source}'
                row=episode(source,models.get(source),(speed,path,sign,scenario,noise),out/'traces'/f'{name}.csv.gz')
                row=dict(pair=pair,speed=speed,path=path,mirror=sign,scenario=scenario,source=source,noise_id=noise,**row)
                if writer is None:writer=csv.DictWriter(f,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(pair,speed,path,sign,scenario,len(rows),flush=True)
    (out/'complete.json').write_text(json.dumps(dict(episodes=len(rows)),indent=2)+'\n')


if __name__=='__main__':main()
