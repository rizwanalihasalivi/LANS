"""One owner for forecasting, common-cost selection, supervision and command fusion."""
from dataclasses import dataclass
import math
import time
import numpy as np
from .physics import Command, Config, advance, baseline, constrain, errors
from .traffic import Inbox, Supervisor, extrapolate


@dataclass(frozen=True)
class Proposal:
    sequence: int
    observed_s: float
    submitted_s: float
    residual: float
    wall_observed: float


def deterministic(state, route, gains):
    e,_ = errors(state,route)
    return float(np.clip(-gains[0]*e[0]-gains[1]*e[2],-.08,.08))


class Pipeline:
    def __init__(self, route, scenario='following', cfg=None, delay=0., gains=(.02,.02), mode='hybrid',
                 clock=None, target_speed=12., deterministic_grid=(), baseline_fn=None, predict_fn=None):
        self.cfg=cfg or Config();self.route=route
        if not math.isfinite(delay) or delay<0 or abs(delay/self.cfg.dt-round(delay/self.cfg.dt))>1e-8:
            raise ValueError('command delay must be a nonnegative multiple of dt')
        if mode not in ('lqr','fixed','deterministic','ppo','hybrid'):raise ValueError('invalid mode')
        if not math.isfinite(target_speed) or target_speed<=0:raise ValueError('positive target speed required')
        if any(not math.isfinite(x) or abs(x)>self.cfg.residual_limit for x in deterministic_grid):
            raise ValueError('deterministic grid exceeds residual authority')
        self.clock=clock or time.monotonic;self.target_speed=target_speed;self.deterministic_grid=tuple(deterministic_grid)
        self.baseline_fn=baseline_fn or baseline;self.predict_fn=predict_fn or advance
        self.delay=delay;self.gains=gains;self.mode=mode
        self.inbox=Inbox();self.supervisor=Supervisor(self.cfg,scenario)
        self.expected=set();self.history=[];self.pending=[]
        self.applied=Command();self.issued=Command();self.proposal=None
        self.last_sequence=-1;self.last_query=-math.inf;self.latency=.0

    def accept(self, proposal, now, wall_now=None):
        wall_now=self.clock() if wall_now is None else wall_now
        valid=(type(proposal.sequence) is int and proposal.sequence>self.last_sequence
               and np.isfinite([proposal.observed_s,proposal.submitted_s,proposal.residual,proposal.wall_observed]).all()
               and 0<=proposal.observed_s<=proposal.submitted_s<=now+1e-9
               and 0<=wall_now-proposal.wall_observed
               and wall_now+self.delay-proposal.wall_observed<=self.cfg.proposal_ttl+1e-9
               and now+self.delay-proposal.observed_s<=self.cfg.proposal_ttl+1e-9
               and abs(proposal.residual)<=self.cfg.residual_limit+1e-9)
        if not valid:return False
        self.proposal=proposal;self.last_sequence=proposal.sequence
        self.latency=max(0.,now-proposal.submitted_s)
        return True

    def reconstruct(self, now):
        p=self.inbox.latest.get('ego')
        if p is None or now-p.observed_s>self.cfg.ego_ttl+1e-9:return None
        z=np.array(p.state,dtype=float);cursor=p.observed_s
        for start,end,command in self.history:
            if end<=cursor+1e-10:continue
            if start>cursor+1e-8:raise ValueError('applied-control history gap')
            until=min(end,now)
            if until>cursor:z=self.predict_fn(z,command,until-cursor);cursor=until
            if cursor>=now-1e-9:break
        if cursor<now-1e-8:raise ValueError('incomplete applied-control history')
        return z

    def forecast(self, now):
        z=self.reconstruct(now)
        if z is None:return None
        cursor=now;command=self.applied
        for due,c in self.pending:
            if due>now+self.delay+1e-9:break
            if due>cursor:z=self.predict_fn(z,command,due-cursor);cursor=due
            command=c
        if now+self.delay>cursor:z=self.predict_fn(z,command,now+self.delay-cursor)
        return z

    def features(self, now, busy=False):
        z=self.forecast(now)
        if z is None:return None
        # Risk assessment for features must not advance hysteresis memory.
        previous=self.supervisor.state
        risk=self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay)
        self.supervisor.state=previous
        e,_=errors(z,self.route);p=self.inbox.latest['ego']
        previews=[z[1]-self.route.geometry(z[0]+z[3]*i*.15)[0] for i in range(1,5)]
        raw=np.array([*e,z[3],*previews,now-p.observed_s,self.latency,
                      min(10.,risk.ttc),min(30.,risk.clearance),risk.max_age,
                      self.applied.steering,self.applied.accel,float(busy)])
        scale=np.array([2.,5.,.5,2.,25.,2.,2.,2.,2.,.4,.2,10.,30.,.4,.5,6.,1.])
        return np.clip(raw/scale,-5,5).astype(np.float32)

    def cost(self, z, first, residual, accel, vehicles, lifetime):
        cfg=self.cfg;previous=self.issued;total=0.;minimum=math.inf
        steps=math.ceil(cfg.horizon/cfg.dt)
        for i in range(steps):
            active=residual if i*cfg.dt<lifetime-1e-9 else 0.
            command=first if i==0 else constrain(Command(self.baseline_fn(z,self.route)+active,accel),previous,cfg)
            z=self.predict_fn(z,command,cfg.dt)
            e,_=errors(z,self.route)
            total += cfg.dt*(8*e[0]**2+2*e[2]**2+.03*command.steering**2
                              +.02*((command.steering-previous.steering)/cfg.dt)**2)
            for _,other,uncertainty in vehicles:
                n=extrapolate(other,(i+1)*cfg.dt)
                clearance=np.linalg.norm(n[:2]-z[:2])-2*cfg.vehicle_radius-cfg.buffer-uncertainty-cfg.uncertainty_rate*(i+1)*cfg.dt
                minimum=min(minimum,float(clearance))
            previous=command
        return float(total),minimum

    def decide(self, now, worker_failed=False):
        start=time.perf_counter();cfg=self.cfg;z=self.forecast(now)
        reason='';costs={};eligible={};source='lqr';selected=0.
        if z is None:
            command=constrain(Command(self.issued.steering,-cfg.max_brake),self.issued,cfg)
            state='DANGER';reason='ego_missing_or_stale';risk=None;source='hold_brake'
        else:
            risk=self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay)
            nominal=float(np.clip((self.target_speed-z[3])*.8,-cfg.max_brake,cfg.max_accel))
            accel=self.supervisor.acceleration(nominal,risk)
            lqr=self.baseline_fn(z,self.route)
            command=constrain(Command(lqr,accel),self.issued,cfg)
            candidates={'lqr':(0.,cfg.horizon)}
            if self.mode=='fixed':candidates['fixed']=(.02,cfg.horizon)
            if self.mode in ('deterministic','hybrid'):
                candidates['deterministic']=(deterministic(z,self.route,self.gains),cfg.horizon)
                for residual in self.deterministic_grid:
                    candidates[f'optimized_{residual:+.3f}']=(residual,cfg.horizon)
            p=self.proposal;wall=self.clock()
            fresh=(p is not None and now+self.delay-p.observed_s<cfg.proposal_ttl-1e-9
                   and 0<=wall-p.wall_observed and wall+self.delay-p.wall_observed<cfg.proposal_ttl-1e-9)
            if self.mode in ('ppo','hybrid') and fresh and not worker_failed:
                candidates['ppo']=(p.residual,min(cfg.horizon,cfg.proposal_ttl-(now+self.delay-p.observed_s),
                                                cfg.proposal_ttl-(wall+self.delay-p.wall_observed)))
            else:reason='worker_failed' if worker_failed else 'proposal_absent_or_expired'
            # Missing traffic knowledge, danger or dead inference forces analytical steering.
            if risk.state=='DANGER' or worker_failed:
                candidates={'lqr':(0.,cfg.horizon)}
                reason='traffic_missing_or_stale' if risk.missing else ('risk_danger' if risk.state=='DANGER' else 'worker_failed')
            best=math.inf
            for name,(residual,lifetime) in candidates.items():
                first=constrain(Command(lqr+residual,accel),self.issued,cfg)
                value,clear=self.cost(z.copy(),first,residual,accel,risk.vehicles,lifetime)
                costs[name]=value;eligible[name]=clear>=0
                # Baseline is always retained as fallback, never called certified safe.
                if name=='lqr':best=value if clear>=0 else math.inf
                elif clear>=0 and value<best-1e-8:
                    best=value;command=first;source=name;selected=residual
            if not eligible.get(source,False):
                command=constrain(Command(lqr,-cfg.max_brake),self.issued,cfg)
                source='lqr';selected=0.;reason='no_feasible_prediction'
            if source=='ppo' and self.clock()+self.delay-p.wall_observed>=cfg.proposal_ttl:
                command=constrain(Command(lqr,accel),self.issued,cfg)
                source='lqr';selected=0.;reason='proposal_expired_before_issue'
            state=risk.state
        self.pending.append((now+self.delay,command));self.issued=command
        return dict(source=source,residual=selected,risk=state,reason=reason,costs=costs,eligible=eligible,
                    critical_id=risk.critical_id if risk else '',ttc=risk.ttc if risk else math.inf,
                    clearance=risk.clearance if risk else math.inf,traffic_age=risk.max_age if risk else 0.,
                    missing=list(risk.missing) if risk else [],ego_age=now-self.inbox.latest['ego'].observed_s if 'ego' in self.inbox.latest else None,
                    proposal_age=now+self.delay-self.proposal.observed_s if self.proposal else None,
                    proposal_wall_age=self.clock()+self.delay-self.proposal.wall_observed if self.proposal else None,
                    issued_steering=command.steering,issued_accel=command.accel,
                    control_ms=1000*(time.perf_counter()-start))

    def apply(self, now, state, stiffness=1.):
        while self.pending and self.pending[0][0]<=now+1e-9:
            _,self.applied=self.pending.pop(0)
        result=advance(state,self.applied,self.cfg.dt,stiffness)
        self.history.append((now,now+self.cfg.dt,self.applied))
        self.history=[h for h in self.history if h[1]>=now-2*self.cfg.ego_ttl]
        return result
