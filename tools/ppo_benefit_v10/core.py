"""Causal queue-aware PPO study; shared v8 source is imported unchanged."""
from pathlib import Path
import json,math
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from integrations.unified_lans.controller import Proposal
from integrations.unified_lans.physics import Command,constrain,errors
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_control_v8.control import Controller
from tools.unified_control_v9.learning import setup,training_case

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/ppo-benefit-v10'
PARAMS=dict(quality_factor=1.1,early_id=True,tracking_only=False,adaptive=True,mpc=True)
CONTRACT='v8-queue-model30-after-issue-delay50-v1'


def dump(path,value):path.write_text(json.dumps(clean(value),indent=2,allow_nan=False,default=lambda x:x.tolist())+'\n')


def predicted_application(c,now):
    """Only current received state, estimated model and already-issued queue."""
    state=c.reconstruct(now)
    if state is None:return None
    until=now+.05+c.delay;cursor=now;command=c.applied
    for due,cmd in c.pending:
        if due>until+1e-9:break
        if due>cursor:state=c.predict(state,command,due-cursor);cursor=due
        command=cmd
    if until>cursor:state=c.predict(state,command,until-cursor)
    return state


def observation(c,now,last_action):
    public=c.features(now)
    if public is None:return np.zeros(30,np.float32),False
    future=predicted_application(c,now);e,_=errors(future,c.route)
    queue=[(due,cmd) for due,cmd in c.pending if due>now+1e-9]
    front=queue[0] if queue else (now,c.issued);back=queue[-1] if queue else front
    extra=[(c.stiffness_estimate-1)/.3,c.stiffness_uncertainty/.3,c.delay/.15,last_action,
        c.issued.steering/.5,c.issued.accel/6,front[1].steering/.5,front[1].accel/6,
        back[1].steering/.5,back[1].accel/6,(front[0]-now)/.15,e[0]/2,e[2]/.5]
    result=np.r_[public,extra].astype(np.float32)
    assert result.shape==(30,) and np.isfinite(result).all()
    return np.clip(result,-5,5),True


def teacher(c,now):
    """Return normalized scalar label; no physics truth or future packet reads."""
    if c.delay+.05>=c.cfg.proposal_ttl-1e-9:return 0.,dict(reason='strict_expiry',gain=0.)
    z=predicted_application(c,now)
    if z is None:return 0.,dict(reason='missing_ego',gain=0.)
    old=c.supervisor.state
    risk=c.supervisor.assess(z,c.inbox,c.expected,now+.05,now+.05+c.delay)
    c.supervisor.state=old
    if risk.state=='DANGER':return 0.,dict(reason='danger',gain=0.)
    accel=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-z[3]),-6,2.5)),risk)
    saved=(c._plan,c._plan_residual,c._cost_reference)
    try:
        c._plan=None;c._plan_residual=None;c._cost_reference=None
        lqr=c.baseline_fn(z,c.route);base=constrain(Command(lqr,accel),c.issued,c.cfg)
        value,margin=c.cost(z.copy(),base,0.,accel,risk.vehicles,.05)
        best=value if margin>=0 else math.inf;chosen=0.;reference=value;count=0
        for residual in np.linspace(-.08,.08,65):
            if abs(residual)<1e-12:continue
            first=constrain(Command(lqr+residual,accel),c.issued,c.cfg)
            cost,clear=c.cost(z.copy(),first,float(residual),accel,risk.vehicles,.05)
            if clear>=0:
                count+=1
                if cost<best-1e-8:best=cost;chosen=float(residual)
        gain=max(0.,(reference-best)/max(abs(reference),1e-8)) if math.isfinite(best) else 0.
        return chosen/.08,dict(reason='searched',gain=gain,eligible=count,estimated_state=z.tolist())
    finally:c._plan,c._plan_residual,c._cost_reference=saved


class Env(gym.Env):
    def __init__(self,trace=None,kind='new',model=None):
        super().__init__();self.observation_space=spaces.Box(-5.,5.,(30,),np.float32)
        self.action_space=spaces.Box(-1.,1.,(1,),np.float32)
        self.trace_path=trace;self.trace=None if trace is None else Path(trace).open('x')
        self.episode=-1;self.pipe=None;self.shadow=None;self.kind=kind;self.model=model
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed);self.close_controllers()
        self.case=dict(options['case']) if options and 'case' in options else training_case(self.np_random)
        self.pipe,self.clock,self.ego,self.npcs,self.net=setup(self.case,'hybrid' if self.kind!='lqr' else 'lqr',Controller,
            dict(PARAMS,adaptive=self.kind!='lqr',mpc=self.kind!='lqr'),grid=self.kind!='lqr')
        self.shadow,self.sclock,self.sego,_,self.snet=setup(self.case,'deterministic',Controller,PARAMS,grid=True)
        self.pipe.expected=set(self.npcs);self.tick=0;self.seq=0;self.last_action=0.;self.episode+=1;self.done=False
        self.net.emit(0.,self.ego,self.npcs,self.pipe.inbox);self.snet.emit(0.,self.sego,self.npcs,self.shadow.inbox)
        self.decision=self.pipe.decide(0.);self.sdecision=self.shadow.decide(0.)
        self.obs,self.valid=observation(self.pipe,0.,0.)
        return self.obs,{}
    def step(self,action):
        if self.done:raise RuntimeError('reset required')
        a=np.asarray(action).reshape(-1)
        if a.shape!=(1,) or not np.isfinite(a).all():raise ValueError('finite scalar required')
        now=self.tick*.05;proposal=None
        if self.valid and self.kind not in ('adaptive','lqr'):
            self.seq+=1;self.last_action=float(np.clip(a[0],-1,1))
            proposal=Proposal(self.seq,self.pipe.inbox.latest['ego'].observed_s,now,.08*self.last_action,now)
        before=self.ego.copy();sbefore=self.sego.copy();previous=self.pipe.applied;sprevious=self.shadow.applied
        decision=self.decision;sdecision=self.sdecision
        self.ego=self.pipe.apply(now,self.ego,self.case['stiffness']);self.sego=self.shadow.apply(now,self.sego,self.case['stiffness'])
        move_npcs(self.npcs,.05,self.pipe.route,self.case['scenario'])
        actual=truth_metrics(self.ego,self.npcs,self.pipe.route,self.pipe.cfg);shadow=truth_metrics(self.sego,self.npcs,self.shadow.route,self.shadow.cfg)
        rate=(self.pipe.applied.steering-previous.steering)/.05;srate=(self.shadow.applied.steering-sprevious.steering)/.05
        def cost(truth,rr,cmd):return 8*truth['error']**2+4*truth['heading_error']**2+.04*rr**2+.002*cmd.accel**2
        failed=bool(actual['collision'] or actual['corridor_exceeded'])
        ac=cost(actual,rate,self.pipe.applied);bc=cost(shadow,srate,self.shadow.applied)
        alternatives=[v for k,v in decision['costs'].items() if k!='ppo' and decision['eligible'].get(k,False)]
        incremental=0.
        if decision['source']=='ppo' and alternatives:
            ref=min(alternatives);incremental=float(np.clip((ref-decision['costs']['ppo'])/max(abs(ref),1e-8),0,1))
        reward=float(np.clip(1000*(bc-ac),-5,5)+incremental-20*failed)
        self.tick+=1;self.clock.now=self.tick*.05;self.sclock.now=self.clock.now
        self.done=failed or self.tick>=120;accepted=None
        if not self.done:
            self.net.emit(self.clock.now,self.ego,self.npcs,self.pipe.inbox);self.snet.emit(self.clock.now,self.sego,self.npcs,self.shadow.inbox)
            if proposal is not None:accepted=self.pipe.accept(proposal,self.clock.now)
            self.decision=self.pipe.decide(self.clock.now);self.sdecision=self.shadow.decide(self.clock.now)
            self.obs,self.valid=observation(self.pipe,self.clock.now,self.last_action)
        else:self.obs=np.zeros(30,np.float32);self.valid=False
        row=dict(episode=self.episode,tick=self.tick-1,time_s=now,case=self.case,action=float(a[0]),observation_next=self.obs,
            state_before=before,state_after=self.ego,shadow_before=sbefore,shadow_after=self.sego,npc_truth=self.npcs,
            decision=decision,shadow_decision=sdecision,truth=actual,shadow_truth=shadow,
            applied_steering=self.pipe.applied.steering,applied_accel=self.pipe.applied.accel,
            shadow_steering=self.shadow.applied.steering,shadow_accel=self.shadow.applied.accel,
            steering_rate=rate,shadow_rate=srate,reward=reward,actual_cost=ac,shadow_cost=bc,incremental_reward=incremental,
            response_accepted_after_step=accepted,terminated=failed,truncated=self.tick>=120 and not failed)
        if self.trace is not None:self.trace.write(json.dumps(clean(row),allow_nan=False,default=lambda x:x.tolist())+'\n')
        return self.obs,reward,failed,self.tick>=120 and not failed,row
    def close_controllers(self):
        for c in (self.pipe,self.shadow):
            if c is not None and hasattr(c,'close'):c.close()
    def close(self):
        self.close_controllers()
        if self.trace is not None:self.trace.close();self.trace=None
