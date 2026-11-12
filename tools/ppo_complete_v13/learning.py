"""Causal current-tick anchor policy and an actual finite-horizon RMSE task."""
from dataclasses import dataclass
from pathlib import Path
import json,math
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from integrations.unified_lans.physics import Command,errors
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_control_v9.learning import setup
from tools.ppo_benefit_v10.core import PARAMS

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/ppo-complete-v13'
CONTRACT='v13-current-anchor55-correction8-finite120-v1'
OBSERVATION_DIM=55;ACTION_DIM=8;HORIZON=120


def controller_class():
    from .plans import PlanMixin
    from .safety import Controller as SafeController
    class Controller(PlanMixin,SafeController):pass
    return Controller


def curriculum(rng):
    case=dict(stage='v13_training',scenario=str(rng.choice(['following','merge','crossing','curved'])),
        speed=float(rng.choice([8.,12.,16.])),delay=float(rng.choice([0.,.05,.1])),mirror=int(rng.choice([-1,1])),
        stiffness=float(rng.uniform(.75,1.25)),lateral=float(rng.uniform(.15,.45)),heading=float(rng.uniform(-.02,.02)),
        phase=float(rng.uniform(-5,28)),amplitude=float(rng.uniform(.85,1.3)),npc_x_shift=float(rng.uniform(-5,5)),
        npc_speed_scale=float(rng.uniform(.75,1.25)),network='nominal',network_seed=int(rng.integers(1_200_000_000,1_900_000_000)))
    case['lateral']*=case['mirror'];return case


@dataclass
class RunningStats:
    """Only received ego samples and known applied controls; no plant truth."""
    error_sq:float=0.
    heading_sq:float=0.
    rate_sq:float=0.
    received_samples:int=0
    last_sequence:int=-1
    last_tick:float=-1.
    previous_applied:float=0.
    proposal_observed:float|None=None
    proposal_wall:float|None=None

    def ingest(self,c,now):
        if now<self.last_tick-1e-9:raise ValueError('running statistics cannot move backwards')
        if now>self.last_tick+1e-9:
            if now>0:
                rate=(c.applied.steering-self.previous_applied)/c.cfg.dt
                self.rate_sq+=rate*rate
            self.previous_applied=c.applied.steering;self.last_tick=float(now)
        p=c.inbox.latest.get('ego')
        if p is not None and p.sequence>self.last_sequence:
            self.last_sequence=p.sequence
            if p.observed_s>0:
                e,_=errors(np.asarray(p.state),c.route)
                self.error_sq+=float(e[0]**2);self.heading_sq+=float(e[2]**2);self.received_samples+=1

    def note_proposal(self,p):
        self.proposal_observed=float(p.observed_s);self.proposal_wall=float(p.wall_observed)


def application_forecast(c,now):
    """Current issue applies at now+FIFO delay, with no invented service tick."""
    z=c.reconstruct(now)
    if z is None:return None
    until=now+c.delay;cursor=now;command=c.applied
    for due,cmd in c.pending:
        if due>until+1e-9:break
        if due>cursor:z=c.predict(z,command,due-cursor);cursor=due
        command=cmd
    if until>cursor:z=c.predict(z,command,until-cursor)
    return z


def observe(c,ctx,running,last_action,*,terminal=False):
    now=float(ctx.now);running.ingest(c,now);public=c.features(now)
    if public is None:return np.zeros(OBSERVATION_DIM,np.float32),False
    future=application_forecast(c,now)
    if future is None:return np.zeros(OBSERVATION_DIM,np.float32),False
    e,_=errors(future,c.route);last=np.asarray(last_action,float)
    if last.shape!=(8,) or not np.isfinite(last).all():raise ValueError('eight finite previous coefficients required')
    queue=[(due,cmd) for due,cmd in c.pending if due>now+1e-9]
    front=queue[0] if queue else (now,c.issued);back=queue[-1] if queue else front
    extra=[(c.stiffness_estimate-1)/.3,c.stiffness_uncertainty/.3,c.delay/.15,last[0],
        c.issued.steering/.5,c.issued.accel/6,front[1].steering/.5,front[1].accel/6,
        back[1].steering/.5,back[1].accel/6,(front[0]-now)/.15,e[0]/2,e[2]/.5]
    ages=[1.,1.] if running.proposal_observed is None else [(now+c.delay-running.proposal_observed)/.15,
        (c.clock()+c.delay-running.proposal_wall)/.15]
    previous=[ctx.previous.steering/.5,ctx.previous.accel/6]
    left=max(0.,1-now/(HORIZON*c.cfg.dt))
    energies=[math.sqrt(running.error_sq/HORIZON)/.25,
        running.heading_sq/(HORIZON*.02**2),running.rate_sq/(HORIZON*.2**2)]
    value=np.r_[public,extra,last,ages,previous,ctx.anchor_features,left,energies].astype(np.float32)
    assert value.shape==(OBSERVATION_DIM,) and np.isfinite(value).all()
    return np.clip(value,-5,5),True


def rmse_reward(sum_before,error,steps_after,failed=False,scale=100.):
    if not 1<=steps_after<=HORIZON or sum_before<0:raise ValueError('invalid finite-horizon score state')
    after=float(sum_before+error*error)
    if failed:after+=(HORIZON-steps_after)*6.25
    return float(scale*(math.sqrt((sum_before+1e-12)/HORIZON)-math.sqrt((after+1e-12)/HORIZON))),after


def terminal_constraints(heading_sq,rate_sq,progress,reference,failed):
    """Declared additional constraints; privileged shadow is reward-only."""
    if not reference:return dict(heading_penalty=0.,rate_penalty=0.,progress_penalty=0.,failure_penalty=-20.*failed)
    heading_ratio=math.sqrt(heading_sq/max(reference['heading_sq'],1e-8))
    rate_ratio=math.sqrt(rate_sq/max(reference['rate_sq'],1e-8))
    progress_ratio=progress/max(reference['progress_m'],1e-6)
    return dict(heading_penalty=-20.*max(0.,heading_ratio-1.05),rate_penalty=-20.*max(0.,rate_ratio-1.05),
        progress_penalty=-100.*max(0.,.995-progress_ratio)-5.*(progress_ratio<.99),failure_penalty=-20.*failed)


class Env(gym.Env):
    def __init__(self,trace=None,controller_kwargs=None,case_sampler=curriculum):
        super().__init__();self.observation_space=spaces.Box(-5.,5.,(OBSERVATION_DIM,),np.float32)
        self.action_space=spaces.Box(-1.,1.,(ACTION_DIM,),np.float32)
        self.trace=None if trace is None else Path(trace).open('x');self.kwargs=dict(controller_kwargs or {})
        self.case_sampler=case_sampler;self.episode=-1;self.done=True;self.pipe=None

    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        from .safety import Controller as SafeController
        self.case=dict(options['case']) if options and 'case' in options else self.case_sampler(self.np_random)
        self.pipe,self.clock,self.ego,self.npcs,self.net=setup(self.case,'deterministic',controller_class(),dict(PARAMS,**self.kwargs),grid=True)
        self.shadow,self.sclock,self.sego,_,self.snet=setup(self.case,'lqr',SafeController,dict(PARAMS,adaptive=False,mpc=False),grid=False)
        self.tick=0;self.sequence=0;self.last=np.zeros(8);self.running=RunningStats();self.done=False;self.episode+=1
        self.sum_error=0.;self.sum_heading=0.;self.sum_rate=0.;self.shadow_heading=0.;self.shadow_rate=0.
        self.net.emit(0.,self.ego,self.npcs,self.pipe.inbox);self.snet.emit(0.,self.sego,self.npcs,self.shadow.inbox)
        self.ctx=self.pipe.prepare(0.);self.shadow_decision=self.shadow.decide(0.)
        self.obs,self.valid=observe(self.pipe,self.ctx,self.running,self.last)
        return self.obs.copy(),dict(episode_id=self.episode)

    def step(self,action):
        if self.done:raise RuntimeError('reset required')
        from .plans import CorrectionProposal
        action=np.asarray(action,float)
        if action.shape!=(8,) or not np.isfinite(action).all():raise ValueError('eight finite coefficients required')
        action=np.clip(action,-1,1);now=self.tick*.05;query=self.obs.copy();proposal=None;before=self.ego.copy();sbefore=self.sego.copy()
        if self.valid:
            self.sequence+=1
            proposal=CorrectionProposal(self.sequence,self.ctx.observed_s,now,self.ctx.wall_started,tuple(action))
            self.running.note_proposal(proposal);self.last=action.copy()
        decision=self.pipe.finish(self.ctx,proposal);shadow_decision=self.shadow_decision.copy()
        previous=self.pipe.applied;sprev=self.shadow.applied
        self.ego=self.pipe.apply(now,self.ego,self.case['stiffness']);self.sego=self.shadow.apply(now,self.sego,self.case['stiffness'])
        move_npcs(self.npcs,.05,self.pipe.route,self.case['scenario'])
        truth=truth_metrics(self.ego,self.npcs,self.pipe.route,self.pipe.cfg);st=truth_metrics(self.sego,self.npcs,self.shadow.route,self.shadow.cfg)
        rate=(self.pipe.applied.steering-previous.steering)/.05;srate=(self.shadow.applied.steering-sprev.steering)/.05
        failed=bool(truth['collision'] or truth['corridor_exceeded']);self.tick+=1
        primary,new_sum=rmse_reward(self.sum_error,truth['error'],self.tick,failed);self.sum_error=new_sum
        self.sum_heading+=truth['heading_error']**2;self.sum_rate+=rate*rate
        self.shadow_heading+=st['heading_error']**2;self.shadow_rate+=srate*srate
        self.done=failed or self.tick==HORIZON;parts=dict(rmse_reward=primary)
        if self.done:parts.update(terminal_constraints(self.sum_heading,self.sum_rate,float(self.ego[0]),
            dict(heading_sq=self.shadow_heading,rate_sq=self.shadow_rate,progress_m=float(self.sego[0])),failed))
        self.clock.now=self.tick*.05;self.sclock.now=self.clock.now
        self.net.emit(self.clock.now,self.ego,self.npcs,self.pipe.inbox);self.snet.emit(self.clock.now,self.sego,self.npcs,self.shadow.inbox)
        if not self.done:
            self.ctx=self.pipe.prepare(self.clock.now);self.shadow_decision=self.shadow.decide(self.clock.now)
            self.obs,self.valid=observe(self.pipe,self.ctx,self.running,self.last)
        else:
            # No further command is queued after the finite task. The terminal
            # query still contains the received final state and causal history.
            from types import SimpleNamespace
            terminal_ctx=SimpleNamespace(now=self.clock.now,previous=self.pipe.issued,anchor_features=self.ctx.anchor_features)
            self.obs,self.valid=observe(self.pipe,terminal_ctx,self.running,self.last,terminal=True)
        reward=float(sum(parts.values()))
        row=dict(**decision,**truth,episode_id=self.episode,case=self.case,tick=self.tick-1,time_s=now,
            observation=query,observation_next=self.obs,label=action,state_before=before,state_after=self.ego,
            shadow_before=sbefore,shadow_after=self.sego,shadow_truth=st,
            shadow_decision=shadow_decision,shadow_steering=self.shadow.applied.steering,shadow_accel=self.shadow.applied.accel,
            npc_truth={name:z.copy() for name,z in self.npcs.items()},
            applied_steering=self.pipe.applied.steering,applied_accel=self.pipe.applied.accel,steering_rate=rate,shadow_rate=srate,
            score_error_sq=self.sum_error,heading_energy=self.sum_heading,rate_energy=self.sum_rate,
            reward_parts=parts,reward=reward,terminated=self.done,truncated=False,terminal_reason='failure' if failed else ('horizon' if self.done else ''),
            proposal=None if proposal is None else dict(sequence=proposal.sequence,observed_s=proposal.observed_s,submitted_s=proposal.submitted_s,
                wall_observed=proposal.wall_observed,coefficients=list(proposal.coefficients)))
        if self.trace is not None:
            self.trace.write(json.dumps(clean(row),allow_nan=False,default=lambda a:a.tolist())+'\n')
            if self.done:self.trace.flush()
        return self.obs.copy(),reward,self.done,False,row

    def close(self):
        if self.trace is not None:self.trace.close();self.trace=None
