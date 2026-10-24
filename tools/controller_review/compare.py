"""Paired corrected-root evaluation with explicit simulated command availability."""
import argparse
import csv
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from envs.path_tracking_env import PathTrackingEnv
from controllers.policy_bundle import PolicyBundle


def run(method,seed,speed,delay_ticks,policy=None):
    env=PathTrackingEnv(mode='eval',vx=speed)
    obs,_=env.reset(seed=seed,options={'lateral_error':.15,'heading_error':.01})
    pending=None;packet=None;errors=[]; rows=[]
    for tick in range(1000):
        baseline=env.lqr_control(env.state,env.curvature())
        if pending is not None and pending[0]<=tick:
            _,observed,action=pending;packet=(observed,action);pending=None
        if policy is not None and pending is None:
            action,_=policy.predict(obs);action=.08*float(np.asarray(action).item())
            if delay_ticks==0:
                packet=(tick,action)
            else:
                pending=(tick+delay_ticks,tick,action)
        age=(tick-packet[0])*.01 if packet else float('nan')
        command=baseline
        if method=='residual' and packet is not None and age<.05:
            command=float(np.clip(baseline+packet[1],-.5,.5))
        obs,reward,terminated,truncated,info=env.step([command]);errors.append(info['error'])
        rows.append(dict(method=method,seed=seed,speed=speed,delay_ms=delay_ticks*10,tick=tick,
                         observed_time_s=packet[0]*.01 if packet else float('nan'),age_s=age,
                         baseline_rad=baseline,**info))
        if terminated or truncated:
            break
    # Same fixed 10 s horizon across paired methods, including failure tails.
    return dict(method=method,seed=seed,speed=speed,delay_ms=delay_ticks*10,survived=not terminated,
                steps=len(errors),penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(1000-len(errors))*6.25)/1000))),rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--bundle',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    policy=PolicyBundle(a.bundle) if a.bundle else None;summary=[];traces=[]
    for seed in (101,202):
        for speed in (15,20,25):
            for delay in (0,2,10):
                for method in (('lqr','residual') if policy else ('lqr',)):
                    row,trace=run(method,seed,speed,delay,policy if method=='residual' else None)
                    summary.append(row);traces.extend(trace)
    for name,data in [('episodes',summary),('traces',traces)]:
        with (a.output/(name+'.csv')).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)

if __name__=='__main__':
    main()
