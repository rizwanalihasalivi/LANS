"""Actual bundle inference wall timing; no synthetic fallback or tracking claim."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from controllers.policy_bundle import PolicyBundle,digest
from envs.path_tracking_env import PathTrackingEnv


def main():
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    policy=PolicyBundle(a.bundle);env=PathTrackingEnv('eval');obs,_=env.reset(seed=101);times=[]
    for i in range(1100):
        started=time.perf_counter();action,_=policy.predict(obs);elapsed=time.perf_counter()-started
        if i>=100:times.append(elapsed)
        command=np.clip(env.lqr_control(env.state,env.curvature())+.08*float(np.asarray(action).item()),-.5,.5)
        obs,_,done,trunc,_=env.step([command])
        if done or trunc:obs,_=env.reset(seed=101)
    result=dict(kind='synchronous actual CPU inference wall time, not service-age simulation',samples=len(times),
        median_ms=float(np.median(times)*1000),p99_ms=float(np.quantile(times,.99)*1000),policy_sha256=digest(a.bundle/'policy.zip'))
    with a.output.open('x') as f:json.dump(result,f,indent=2)

if __name__=='__main__':main()
