"""Forty-feature, eight-knot PPO environment with causal plan shaping."""
from pathlib import Path
import json
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from integrations.unified_lans.physics import Command
from integrations.unified_lans.traffic import Packet
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v9.learning import setup,training_case
from tools.ppo_benefit_v10.core import observation,predicted_application,PARAMS
from .control import Controller,PlanProposal
from .probe import teacher

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'results/ppo-plan-v11'
CONTRACT='v8-sequence40-knots8-after-issue-delay50-v1'


def features(c,now,last):
    base,valid=observation(c,now,float(last[0]))
    if not valid:return np.zeros(40,np.float32),False
    p=c.plan_proposal
    ages=[1.,1.] if p is None else [(now+c.delay-p.observed_s)/.15,(c.clock()+c.delay-p.wall_observed)/.15]
    value=np.r_[base,last,ages].astype(np.float32);assert value.shape==(40,) and np.isfinite(value).all()
    return np.clip(value,-5,5),True


def shaping(c,now,action):
    if .05+c.delay>=.15-1e-9:return 0.
    z=predicted_application(c,now)
    if z is None:return 0.
    old=c.supervisor.state;risk=c.supervisor.assess(z,c.inbox,c.expected,now+.05,now+.05+c.delay);c.supervisor.state=old
    if risk.state=='DANGER':return 0.
    accel=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-z[3]),-6,2.5)),risk)
    reference,_,_,_=c.score_plan(z,np.zeros(8),0,accel,c.issued,risk.vehicles)
    value,margin,_,_=c.score_plan(z,action,0,accel,c.issued,risk.vehicles)
    if margin<0:return -.25
    return .25*float(np.clip((reference-value)/max(abs(reference),1e-6),-1,1))


class Env(gym.Env):
    def __init__(self,trace=None):
        super().__init__();self.observation_space=spaces.Box(-5.,5.,(40,),np.float32);self.action_space=spaces.Box(-1.,1.,(8,),np.float32)
        self.pipe=None;self.shadow=None;self.episode=-1;self.trace=None if trace is None else Path(trace).open('x')
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed);self.case=dict(options['case']) if options and 'case' in options else training_case(self.np_random)
        self.pipe,self.clock,self.ego,self.npcs,self.net=setup(self.case,'deterministic',Controller,PARAMS,grid=True)
        self.shadow,self.sclock,self.sego,_,self.snet=setup(self.case,'deterministic',Base,PARAMS,grid=True)
        self.tick=0;self.sequence=0;self.last=np.zeros(8);self.done=False;self.episode+=1
        self.net.emit(0.,self.ego,self.npcs,self.pipe.inbox);self.snet.emit(0.,self.sego,self.npcs,self.shadow.inbox)
        self.decision=self.pipe.decide(0.);self.sdecision=self.shadow.decide(0.);self.obs,self.valid=features(self.pipe,0.,self.last)
        return self.obs,{}
    def step(self,action):
        if self.done:raise RuntimeError('reset required')
        action=np.asarray(action,float)
        if action.shape!=(8,) or not np.isfinite(action).all():raise ValueError('finite eight-knot action required')
        action=np.clip(action,-1,1);now=self.tick*.05;query=self.obs.copy();bonus=shaping(self.pipe,now,action) if self.valid else 0.;proposal=None
        if self.valid:
            self.sequence+=1;self.last=action.copy()
            proposal=PlanProposal(self.sequence,self.pipe.inbox.latest['ego'].observed_s,now,now,tuple(action))
        before=self.ego.copy();sbefore=self.sego.copy();prev=self.pipe.applied;sprev=self.shadow.applied;decision=self.decision
        self.ego=self.pipe.apply(now,self.ego,self.case['stiffness']);self.sego=self.shadow.apply(now,self.sego,self.case['stiffness'])
        move_npcs(self.npcs,.05,self.pipe.route,self.case['scenario'])
        truth=truth_metrics(self.ego,self.npcs,self.pipe.route,self.pipe.cfg);st=truth_metrics(self.sego,self.npcs,self.shadow.route,self.shadow.cfg)
        rate=(self.pipe.applied.steering-prev.steering)/.05;srate=(self.shadow.applied.steering-sprev.steering)/.05
        def cost(t,r,c):return 8*t['error']**2+4*t['heading_error']**2+.04*r*r+.002*c.accel*c.accel
        actual=cost(truth,rate,self.pipe.applied);reference=cost(st,srate,self.shadow.applied)
        fail=bool(truth['collision'] or truth['corridor_exceeded']);actual_reward=float(np.clip(1000*(reference-actual),-5,5)-20*fail)
        reward=actual_reward+bonus;self.tick+=1;self.clock.now=self.tick*.05;self.sclock.now=self.clock.now;self.done=fail or self.tick>=120
        accepted=None
        if not self.done:
            self.net.emit(self.clock.now,self.ego,self.npcs,self.pipe.inbox);self.snet.emit(self.clock.now,self.sego,self.npcs,self.shadow.inbox)
            if proposal is not None:accepted=self.pipe.accept_plan(proposal,self.clock.now)
            self.decision=self.pipe.decide(self.clock.now);self.sdecision=self.shadow.decide(self.clock.now)
            self.obs,self.valid=features(self.pipe,self.clock.now,self.last)
        else:self.obs=np.zeros(40,np.float32);self.valid=False
        row=dict(**decision,**truth,episode_id=self.episode,case=self.case,tick=self.tick-1,time_s=now,
            state_before=before,state_after=self.ego,shadow_before=sbefore,shadow_after=self.sego,
            npc_truth={name:z.copy() for name,z in self.npcs.items()},observation=query,observation_next=self.obs,label=action,accepted=accepted,
            applied_steering=self.pipe.applied.steering,applied_accel=self.pipe.applied.accel,steering_rate=rate,
            shadow_steering=self.shadow.applied.steering,shadow_accel=self.shadow.applied.accel,shadow_rate=srate,
            shadow_truth=st,actual_cost=actual,shadow_cost=reference,actual_reward=actual_reward,shaping_reward=bonus,
            reward=reward,terminated=fail,truncated=self.tick>=120 and not fail)
        if self.trace is not None:self.trace.write(json.dumps(clean(row),allow_nan=False,default=lambda x:x.tolist())+'\n')
        return self.obs,reward,fail,self.tick>=120 and not fail,row
    def close(self):
        if self.trace is not None:self.trace.close();self.trace=None


def reconstruct(case,rows):
    """Recover after-issue queries from received states/history, not future truth."""
    c,clock,_,npcs,_=setup(case,'deterministic',Controller,PARAMS,grid=True);last=np.zeros(8);observations=[]
    for i,row in enumerate(rows):
        now=i*.05;clock.now=now;state=np.asarray(row['state_before'])
        c.inbox.ingest(Packet('ego',i,now,tuple(state)),now)
        for name,other in npcs.items():c.inbox.ingest(Packet(name,i,now,tuple(other)),now)
        c.update_model();c.supervisor.state=row['risk']
        assert abs(c.stiffness_estimate-row['stiffness_estimate'])<1e-12
        if i:
            c.plan_proposal=PlanProposal(i,(i-1)*.05,(i-1)*.05,(i-1)*.05,tuple(last));c.plan_sequence=i
        actual=Command(row['issued_steering'],row['issued_accel']);c.pending.append((now+case['delay'],actual));c.issued=actual
        value,valid=features(c,now,last);assert valid;observations.append(value)
        while c.pending and c.pending[0][0]<=now+1e-9:_,c.applied=c.pending.pop(0)
        assert c.applied==Command(row['applied_steering'],row['applied_accel'])
        c.history.append((now,now+.05,c.applied));c.history=[h for h in c.history if h[1]>=now-c.backup_limit_s-c.cfg.ego_ttl]
        npcs={name:np.asarray(z) for name,z in row['npc_truth'].items()};last=np.asarray(row['label'])
    return np.asarray(observations,np.float32)
