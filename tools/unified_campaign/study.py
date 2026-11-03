"""Reproducible logical-time experiments; real-worker timing is a separate stage."""
from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import time
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from integrations.unified_lans.physics import Config, Command, Route, errors
from integrations.unified_lans.controller import Pipeline, Proposal
from integrations.unified_lans.simulation import Network, initial, move_npcs, truth_metrics
from integrations.unified_lans.inference import load_policy, CONTRACT, FEATURES, sha


@dataclass
class Clock:
    now: float = 0.
    def __call__(self):return self.now


@dataclass(frozen=True)
class StudyRoute:
    kind: str
    mirror: int = 1
    phase: float = 0.
    amplitude: float = 1.

    def geometry(self,x):
        y,h,k=Route(self.kind).geometry(x+self.phase)
        d=math.tan(h);dd=k*(1+d*d)**1.5;scale=self.mirror*self.amplitude
        return scale*y,math.atan(scale*d),scale*dd/(1+(scale*d)**2)**1.5


def make_case(stage, index):
    """32 finite grid cells; stage-specific RNG and route phase remain disjoint."""
    rng=np.random.default_rng((110000 if stage=='development' else 910000)+index)
    scenario=['following','merge','crossing','curved'][index//8]
    mirror=1 if (index//4)%2==0 else -1
    speed=[8.,16.][(index//2)%2]
    stiffness=[.8,1.2][index%2]
    return dict(id=index,stage=stage,scenario=scenario,mirror=mirror,speed=speed,stiffness=stiffness,
        lateral=float(rng.uniform(.15,.45))*mirror,heading=float(rng.uniform(-.015,.015)),
        phase=0. if stage=='development' else 12.,amplitude=1. if stage=='development' else 1.15,
        network='nominal',delay=0.,network_seed=(210000 if stage=='development' else 1010000)+index)


def setup(case,mode='hybrid',grid=False):
    scenario=case['scenario'];route0,ego,npcs=initial(scenario,0.)
    route=StudyRoute(route0.kind,case['mirror'],case['phase'],case['amplitude'])
    y,h,_=route.geometry(0.)
    ego=np.array([0.,y+case['lateral'],h+case['heading'],case['speed'],0.,0.])
    for name,n in npcs.items():
        if scenario=='crossing':n[1]*=case['mirror'];n[2]*=case['mirror']
        else:
            n[1]=route.geometry(n[0])[0] if scenario in ('curved','merge') else 0.
            n[2]=route.geometry(n[0])[1] if scenario=='curved' else 0.
            n[3]=max(3.,case['speed']-4.)
    clock=Clock();cfg=Config()
    pipe=Pipeline(route,scenario,cfg,case['delay'],gains=(.04,0.),mode=mode,clock=clock,
                  target_speed=case['speed'],deterministic_grid=(-.08,-.04,0.,.04,.08) if grid else ())
    pipe.expected=set(npcs)
    return pipe,clock,ego,npcs,Network(case['network_seed'],case['network'])


class Env(gym.Env):
    """Training-only randomized cases. No development/reserved case seeds are read."""
    def __init__(self):
        super().__init__();self.observation_space=spaces.Box(-5.,5.,(17,),np.float32)
        self.action_space=spaces.Box(-1.,1.,(1,),np.float32)

    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        idx=int(self.np_random.integers(32));case=make_case('development',idx)
        # Training parameters use this environment's RNG, not evaluation fixtures.
        case.update(lateral=float(self.np_random.uniform(-.5,.5)),heading=float(self.np_random.uniform(-.03,.03)),
                    speed=float(self.np_random.choice([8.,12.,16.])),stiffness=float(self.np_random.uniform(.75,1.25)),
                    phase=float(self.np_random.uniform(-5.,5.)),amplitude=float(self.np_random.uniform(.85,1.1)),
                    network_seed=int(self.np_random.integers(1,100000)),delay=float(self.np_random.choice([0.,.05,.1])))
        self.pipe,self.clock,self.ego,self.npcs,self.net=setup(case,'ppo')
        self.case=case;self.tick=0;self.seq=0;self.done=False
        self.net.emit(0.,self.ego,self.npcs,self.pipe.inbox)
        return self.pipe.features(0.),{}

    def step(self,action):
        if self.done:raise RuntimeError('reset required')
        a=np.asarray(action).reshape(-1)
        if a.shape!=(1,) or not np.isfinite(a).all():raise ValueError('finite scalar action required')
        now=self.clock.now;self.seq+=1
        assert self.pipe.accept(Proposal(self.seq,now,now,float(np.clip(a[0],-1,1))*.08,now),now)
        previous=self.pipe.applied;decision=self.pipe.decide(now)
        self.ego=self.pipe.apply(now,self.ego,self.case['stiffness'])
        move_npcs(self.npcs,.05,self.pipe.route,self.case['scenario'])
        truth=truth_metrics(self.ego,self.npcs,self.pipe.route,self.pipe.cfg)
        rate=(self.pipe.applied.steering-previous.steering)/.05
        reward=1.-2*truth['error']**2-.5*truth['heading_error']**2-.02*rate**2-.002*self.pipe.applied.accel**2
        failed=truth['collision'] or abs(truth['error'])>2.5
        reward-=20*failed;self.tick+=1;self.clock.now=self.tick*.05
        self.net.emit(self.clock.now,self.ego,self.npcs,self.pipe.inbox)
        self.done=bool(failed or self.tick>=120)
        return self.pipe.features(self.clock.now),float(reward),bool(failed),self.tick>=120,dict(**truth,selected=decision['source'])


def run_episode(case,mode,model=None,grid=False,seconds=6.):
    pipe,clock,ego,npcs,net=setup(case,mode,grid)
    rows=[];sequence=0;pending=None
    # One logical request at a time, fixed 50 ms service; no timing claims.
    for tick in range(round(seconds/.05)):
        now=tick*.05;clock.now=now;net.emit(now,ego,npcs,pipe.inbox)
        if pending is not None and pending[0]<=now+1e-9:
            pipe.accept(pending[1],now);pending=None
        if model is not None and pending is None:
            features=pipe.features(now)
            if features is not None:
                action,_=model.predict(features,deterministic=True);sequence+=1
                p=Proposal(sequence,pipe.inbox.latest['ego'].observed_s,now,float(np.asarray(action).ravel()[0])*.08,now)
                pending=(now+.05,p)
        before=ego.copy();previous=pipe.applied;decision=pipe.decide(now)
        ego=pipe.apply(now,ego,case['stiffness']);move_npcs(npcs,.05,pipe.route,case['scenario'])
        truth=truth_metrics(ego,npcs,pipe.route,pipe.cfg)
        rows.append(dict(tick=tick,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),
            npc_truth={k:v.tolist() for k,v in npcs.items()},**truth,**decision,
            applied_steering=pipe.applied.steering,applied_accel=pipe.applied.accel,
            steering_rate=(pipe.applied.steering-previous.steering)/.05))
        if truth['collision'] or abs(truth['error'])>2.5:break
    # Failure penalization keeps early termination from appearing to improve RMSE.
    n=round(seconds/.05);failed=len(rows)<n or any(r['collision'] or r['corridor_exceeded'] for r in rows)
    sse=sum(r['error']**2 for r in rows)+(n-len(rows))*2.5**2
    result=dict(case=case,mode='optimized' if grid else mode,ticks=len(rows),expected_ticks=n,failed=failed,
        rmse_m=math.sqrt(sse/n),heading_rms=math.sqrt(sum(r['heading_error']**2 for r in rows)/len(rows)),
        rate_rms=math.sqrt(sum(r['steering_rate']**2 for r in rows)/len(rows)),
        progress_m=float(ego[0]),min_clearance=min(r['true_clearance'] for r in rows),
        collisions=sum(r['collision'] for r in rows),ppo_ticks=sum(r['source']=='ppo' for r in rows))
    return result,rows
