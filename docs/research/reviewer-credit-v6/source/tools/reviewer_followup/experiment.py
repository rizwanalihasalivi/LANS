import boot
import argparse
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
import time
import numpy as np
import torch
from stable_baselines3 import PPO
from environment import CausalEnv
from supervisor import Controller,observation
from causal_student import load_causal
from train import student_folder
from filtered import FilteredController,P
from nominal_psf import NominalPSF


class FollowupEnv(CausalEnv):
    def __init__(self,profile,case):
        self.profile=profile
        super().__init__(mode='lqr' if profile=='lqr' else 'predictive',case=case)

    def reset(self,**kwargs):
        obs,info=super().reset(**kwargs)
        if self.profile!='lqr':
            self.ctrl=FilteredController(self.profile)
            if self.profile=='nominal_psf':self.ctrl.psf=NominalPSF()
            self.ctrl.previews=self.obs[6:9].astype(float)*.02
        return obs,info

    def _sense(self):
        super()._sense()
        if isinstance(self.ctrl,FilteredController):self.ctrl.previews=self.obs[6:9].astype(float)*.02

    def step_residual(self,residual):
        obs,reward,failed,done,info=super().step_residual(residual)
        info['filtered_residual']=getattr(self.ctrl,'filtered',0.)
        psf=getattr(self.ctrl,'psf',None)
        info.update(solver_horizon=psf.last_horizon if psf else 0,
                    solver_violation=psf.last_violation if psf else 0.)
        return obs,reward,failed,done,info


def episode(profile,source,model,case,trace):
    env=FollowupEnv(profile,case);obs,_=env.reset();rows=[]
    while True:
        start=time.perf_counter_ns();residual=0.;inference=0
        if env.ctrl.pending is None:
            if source=='negative':residual=-.04
            elif source=='positive':residual=.04
            elif model is not None:
                began=time.perf_counter_ns();action,_=model.predict(obs,deterministic=True)
                inference=time.perf_counter_ns()-began
                residual=.08*float(action[0]) if source=='student' else [-.08,-.04,0.,.04,.08][int(action)]
        obs,_,failed,done,row=env.step_residual(residual)
        row.update(inference_ns=inference,processing_ns=time.perf_counter_ns()-start);rows.append(row)
        if failed or done:break
    with gzip.open(trace,'wt',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)
    n=len(rows);scheduled=env.horizon
    result=dict(steps=n,scheduled=scheduled,survived=not failed,
        rmse_m=math.sqrt((sum(r['lateral_error']**2 for r in rows)+(scheduled-n)*6.25)/scheduled),
        heading_rmse_rad=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),
        rate_rms_rad_s=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),
        movement_rad=sum(abs(r['steering_rate'])*.01 for r in rows),active=sum(r['weight']>0 for r in rows),
        psf_calls=env.ctrl.psf.calls if profile=='nominal_psf' else 0,
        psf_fallbacks=env.ctrl.psf.fallbacks if profile=='nominal_psf' else 0)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pair',type=int,choices=range(3),required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);(args.output/'traces').mkdir()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    pair=args.pair
    models={'student':load_causal(student_folder(pair)),
        'ppo':PPO.load(boot.ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{P["seeds"][pair]}/policy.zip',device='cpu')}
    methods=[('lqr','none')]+list(itertools.product(P['profiles'],P['sources']))+[('nominal_psf','ppo')]
    grid=P['screen'];rows=[]
    with (args.output/'episodes.csv').open('w',newline='') as handle:
        writer=None
        for speed,path,mirror,scenario in itertools.product(grid['speeds'],grid['paths'],grid['mirrors'],grid['scenarios']):
            noise=P['noise_base']+pair*100000+speed*1000+grid['paths'].index(path)*100+grid['scenarios'].index(scenario)*10
            for profile,source in methods:
                name=f'{speed}-{path}-{mirror}-{scenario}-{profile}-{source}'
                row=episode(profile,source,models.get(source),(speed,path,mirror,scenario,noise),args.output/'traces'/f'{name}.csv.gz')
                row=dict(pair=pair,speed=speed,path=path,mirror=mirror,scenario=scenario,profile=profile,source=source,noise_id=noise,**row)
                if writer is None:writer=csv.DictWriter(handle,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);handle.flush();rows.append(row)
            print(pair,path,mirror,scenario,len(rows),flush=True)
    (args.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),protocol=P),indent=2)+'\n')


if __name__=='__main__':main()
