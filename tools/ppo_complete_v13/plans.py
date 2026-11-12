"""Causal residual policies anchored to the actual winning analytical rollout.

The reference is feedback on each uncertainty model, rather than a nominal
open-loop copy. Neutral coefficients retain the exact reference. Projection
preserves all original guards and can only tighten the additional learned
heading/rate budget. All final ownership and timestamp checks stay local.
"""
from dataclasses import dataclass,replace
from types import MappingProxyType
import math
import time
import numpy as np
from numba import njit
from integrations.unified_lans.physics import Command
from tools.unified_control_v4.kernels import lqr,step,geometry,rollout

ACTION_DIM=8
DEFAULT_SCALES=(1.,.5,.25,.125,.0625)


def _freeze(value):
    if isinstance(value,dict):return MappingProxyType({k:_freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):return tuple(_freeze(v) for v in value)
    if isinstance(value,np.ndarray):return tuple(_freeze(v) for v in value.tolist())
    if isinstance(value,np.generic):return value.item()
    return value


def _copy(value):
    if isinstance(value,(dict,MappingProxyType)):return {k:_copy(v) for k,v in value.items()}
    if isinstance(value,tuple):return [_copy(v) for v in value]
    return value


@dataclass(frozen=True)
class CorrectionProposal:
    sequence:int
    observed_s:float
    submitted_s:float
    wall_observed:float
    coefficients:tuple


@dataclass(frozen=True)
class Context:
    now:float
    observed_s:float
    wall_started:float
    previous:Command
    state:tuple
    reference_first:float
    reference_residual:float
    acceleration:float
    reference_plan:tuple
    planned:bool
    models:tuple
    vehicles:tuple
    reference_values:tuple
    lqr_values:tuple
    anchor_features:tuple
    eligible:bool
    pending_index:int
    _row:object

    @property
    def row(self):return _copy(self._row)

    @property
    def baseline_row(self):return self.row


@dataclass(frozen=True)
class Score:
    values:tuple
    first:float
    scale:float
    neutral:bool
    admissible:bool
    violations:object

    @property
    def cost(self):return float(np.mean([v[0] for v in self.values]))

    @property
    def physical_margin(self):return float(min(v[1] for v in self.values))

    @property
    def margin(self):
        return self.physical_margin if self.admissible else min(self.physical_margin,-1e-9)


@njit(cache=True)
def anchored_rollout(z,coefficients,scale,amplitude,first,residual,reference_plan,planned,
                     accel,previous,dt,n,stiff,gains,route,npcs,radius,buffer,uncertainty,
                     angle,rate,limit,feedback):
    """Model-specific feedback anchor plus bounded interpolated correction."""
    state=z.copy();cost=0.;margin=1e9;heading=0.;rate_energy=0.;commands=np.empty(n);offsets=np.empty(n)
    for i in range(n):
        base=lqr(state,gains,int(route[0]),route[1],route[2],route[3],feedback)
        where=i*7/max(1,n-1);low=int(math.floor(where));high=min(7,low+1)
        delta=amplitude*scale*((1-(where-low))*coefficients[low]+(where-low)*coefficients[high])
        if i==0:
            offset=residual
            if delta==0.:u=first
            else:
                bounded=min(limit,max(-limit,residual+delta))
                u=min(previous+rate*dt,max(previous-rate*dt,base+bounded))
        else:
            anchor=min(base+limit,max(base-limit,reference_plan[i])) if planned else base
            offset=anchor-base
            desired=anchor if delta==0. else min(base+limit,max(base-limit,anchor+delta))
            u=min(previous+rate*dt,max(previous-rate*dt,desired))
        u=min(angle,max(-angle,u));commands[i]=u;offsets[i]=offset/limit
        state=step(state,u,accel,dt,stiff)
        y,h,_=geometry(state[0],int(route[0]),route[1],route[2],route[3])
        ey=state[1]-y;ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h));slew=(u-previous)/dt
        cost+=dt*(8*ey*ey+2*ep*ep+.03*u*u+.02*slew*slew)
        heading+=dt*ep*ep;rate_energy+=dt*slew*slew;margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for j in range(len(npcs)):
            other=npcs[j];vx=other[3]*math.cos(other[2])-other[4]*math.sin(other[2])
            vy=other[3]*math.sin(other[2])+other[4]*math.cos(other[2])
            dx=other[0]+vx*t-state[0];dy=other[1]+vy*t-state[1]
            margin=min(margin,math.sqrt(dx*dx+dy*dy)-2*radius-buffer-other[6]-uncertainty*t)
        previous=u
    return np.array([cost,margin,heading,rate_energy]),commands,offsets


def _metric_tuples(values):return tuple(tuple(float(x) for x in v) for v in values)


def _npcs(ctx):return np.asarray([(*state,uncertainty) for _,state,uncertainty in ctx.vehicles],float).reshape(-1,7)


class PlanMixin:
    """Compose as ``class Controller(PlanMixin, safety.Controller): pass``.

    ``prepare`` issues one provisional analytical command. ``finish`` either
    retains it exactly or atomically replaces that same pending command. A
    single context can finish once, and no external command is applied here.
    """
    def __init__(self,*args,correction_amplitude=.02,projection_scales=DEFAULT_SCALES,
                 anchor_quality_factor=1.,learned_heading_factor=None,learned_rate_factor=None,**kwargs):
        super().__init__(*args,**kwargs)
        if not 0<correction_amplitude<=self.cfg.residual_limit:raise ValueError('correction amplitude exceeds residual authority')
        if not projection_scales or any(not 0<s<=1 for s in projection_scales):raise ValueError('bounded positive projection scales required')
        heading=anchor_quality_factor if learned_heading_factor is None else learned_heading_factor
        rate_factor=anchor_quality_factor if learned_rate_factor is None else learned_rate_factor
        if any(factor is not None and not 0<factor<=1.1 for factor in (heading,rate_factor)):
            raise ValueError('additional quality factors cannot exceed the original budget')
        if (self.cfg.steering_limit,self.cfg.steering_rate,self.cfg.residual_limit,self.cfg.proposal_ttl,self.cfg.horizon)!=(.5,.6,.08,.15,2.):
            raise ValueError('v13 requires the original physical, horizon and age limits')
        self.correction_amplitude=float(correction_amplitude);self.projection_scales=tuple(float(s) for s in projection_scales)
        self.learned_heading_factor=None if heading is None else float(heading)
        self.learned_rate_factor=None if rate_factor is None else float(rate_factor)
        self._prepared=None;self._last_finished=None;self._proposal_sequence=-1
        self._prepared_history=None;self._last_finished_history=None
        self.last_anchor_features=tuple(np.zeros(9));self.last_plan_score=None

    def _history_marker(self):
        # Both the Python plant and native adapter append actual applied-input
        # intervals. A delayed queue entry can remain pending after a physical
        # step, so its continued presence alone cannot permit a late rollback.
        return (len(self.history),self.history[-1] if self.history else None)

    def _kernel_args(self,ctx):
        c=self.cfg
        return (ctx.acceleration,ctx.previous.steering,c.dt,round(c.horizon/c.dt),self._gains,self._route,
                _npcs(ctx),c.vehicle_radius,c.buffer,c.uncertainty_rate,c.steering_limit,c.steering_rate,
                c.residual_limit,self.feedback_stiffness)

    def prepare(self,now):
        if self._prepared is not None:raise RuntimeError('finish the prior prepared decision before preparing another')
        now=float(now);started=float(self.clock())
        if not math.isfinite(now) or now<0 or not math.isfinite(started):raise ValueError('finite current decision times required')
        if self._last_finished is not None and now<self._last_finished.now+self.cfg.dt-1e-9:
            raise ValueError('one provisional decision per physical control interval is required')
        previous=self.issued;before=len(self.pending);history=self._history_marker()
        row=super().decide(now)
        if len(self.pending)!=before+1:raise RuntimeError('analytical owner must issue exactly one provisional command')
        p=self.inbox.latest.get('ego');z=self.forecast(now)
        observed=now if p is None else p.observed_s
        planned=bool(row.get('planned_candidate_selected') and self._plan is not None)
        plan=np.asarray(self._plan,float).copy() if planned else np.zeros(round(self.cfg.horizon/self.cfg.dt))
        prior=self.supervisor.state
        risk=None if z is None else self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay)
        self.supervisor.state=prior
        vehicles=() if risk is None else tuple((name,tuple(float(x) for x in other),float(u)) for name,other,u in risk.vehicles)
        center=self.stiffness_estimate if self.adaptive else 1.;width=self.stiffness_uncertainty
        models=(max(.7,center-width),center,min(1.3,center+width)) if self.adaptive else (.7,1.,1.3)
        cfg=self.cfg;first=float(row['issued_steering']);accel=float(row['issued_accel']);residual=float(row.get('residual',0.))
        values=[];baseline=[];anchor=np.zeros(9)
        if z is not None:
            npcs=np.asarray([(*s,u) for _,s,u in vehicles],float).reshape(-1,7)
            base=float(np.clip(self.baseline_fn(z,self.route),previous.steering-cfg.steering_rate*cfg.dt,previous.steering+cfg.steering_rate*cfg.dt))
            base=float(np.clip(base,-cfg.steering_limit,cfg.steering_limit))
            for model in models:
                args=(z,first,accel,previous.steering,cfg.dt,cfg.horizon,model,self._gains,self._route,npcs,
                    cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,self.feedback_stiffness)
                values.append(rollout(*args,plan if planned else None))
                base_args=(z,base,accel,previous.steering,cfg.dt,cfg.horizon,model,self._gains,self._route,npcs,
                    cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,self.feedback_stiffness)
                baseline.append(rollout(*base_args))
            _,_,profile=anchored_rollout(z,np.zeros(8),0.,self.correction_amplitude,first,residual,plan,planned,
                accel,previous.steering,cfg.dt,len(plan),center,self._gains,self._route,npcs,cfg.vehicle_radius,
                cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,self.feedback_stiffness)
            anchor[:8]=profile[np.rint(np.linspace(0,len(plan)-1,8)).astype(int)];anchor[8]=float(planned)
        else:
            values=np.tile([1e30,-1e30,1e30,1e30],(3,1));baseline=values.copy();z=np.zeros(6)
        eligible=bool(row.get('eligible',{}).get(row.get('source'),False) and not row.get('ego_backup')
            and row.get('risk')!='DANGER' and not row.get('safety_active',False) and min(v[1] for v in values)>=0)
        ctx=Context(float(now),float(observed),float(started),previous,tuple(float(x) for x in z),first,residual,
            accel,tuple(float(x) for x in plan),planned,tuple(float(x) for x in models),vehicles,
            _metric_tuples(values),_metric_tuples(baseline),tuple(float(x) for x in anchor),eligible,before,_freeze(row))
        self._prepared=ctx;self._prepared_history=history;self.last_anchor_features=ctx.anchor_features;return ctx

    def score_candidate(self,ctx,coefficients,scale=1.):
        if ctx is not self._prepared:raise ValueError('only the current owner context may be scored')
        a=np.asarray(coefficients,float).copy()
        if a.shape!=(8,) or not np.isfinite(a).all() or np.max(abs(a))>1+1e-12:raise ValueError('eight finite normalized coefficients required')
        if not math.isfinite(scale) or not 0<=scale<=1:raise ValueError('bounded finite scale required')
        neutral=bool(np.max(abs(a))*scale<=1e-12)
        if neutral:
            return Score(ctx.reference_values,ctx.reference_first,float(scale),True,ctx.eligible,
                MappingProxyType(dict(cost_dominance=0.,heading=0.,rate=0.,anchor_heading=0.,anchor_rate=0.,physical=0.)))
        args=self._kernel_args(ctx);values=[];first=ctx.reference_first
        for model in ctx.models:
            v,commands,_=anchored_rollout(np.asarray(ctx.state),a,scale,self.correction_amplitude,
                ctx.reference_first,ctx.reference_residual,np.asarray(ctx.reference_plan),ctx.planned,
                args[0],args[1],args[2],args[3],model,*args[4:])
            values.append(v);first=float(commands[0])
        result=np.asarray(values);lqr_ref=np.asarray(ctx.lqr_values);anchor_ref=np.asarray(ctx.reference_values)
        def violation(candidate,cap):
            if np.isinf(cap).all():return 0.
            return float(max(0.,np.max((candidate-cap)/np.maximum(abs(cap),1e-8))))
        limits=dict(cost_dominance=lqr_ref[:,0]-1e-9,heading=1.21*lqr_ref[:,2]+2e-6,
            rate=1.21*lqr_ref[:,3]+1e-5,
            anchor_heading=np.full(3,np.inf) if self.learned_heading_factor is None else self.learned_heading_factor**2*anchor_ref[:,2]+2e-6,
            anchor_rate=np.full(3,np.inf) if self.learned_rate_factor is None else self.learned_rate_factor**2*anchor_ref[:,3]+1e-5)
        violations=dict(cost_dominance=violation(result[:,0],limits['cost_dominance']),
            heading=violation(result[:,2],limits['heading']),rate=violation(result[:,3],limits['rate']),
            anchor_heading=violation(result[:,2],limits['anchor_heading']),anchor_rate=violation(result[:,3],limits['anchor_rate']),
            physical=float(max(0.,-np.min(result[:,1]))))
        # Original cost dominance is strict; every quality and physical limit is
        # unchanged, with an additional anchored learned-quality check.
        valid=bool(ctx.eligible and np.all(result[:,0]<limits['cost_dominance'])
            and np.all(result[:,2]<=limits['heading']) and np.all(result[:,3]<=limits['rate'])
            and np.all(result[:,2]<=limits['anchor_heading']) and np.all(result[:,3]<=limits['anchor_rate'])
            and np.min(result[:,1])>=0)
        return Score(_metric_tuples(result),first,float(scale),False,valid,MappingProxyType(violations))

    def _proposal_valid(self,ctx,p):
        if not isinstance(p,CorrectionProposal) or type(p.sequence) is not int or p.sequence<=self._proposal_sequence:return False
        try:
            a=np.asarray(p.coefficients,float);wall=self.clock()
            return bool(a.shape==(8,) and np.isfinite(a).all() and max(abs(a))<=1+1e-12
                and np.isfinite([p.observed_s,p.submitted_s,p.wall_observed,wall]).all()
                and abs(p.observed_s-ctx.observed_s)<=1e-9 and abs(p.submitted_s-ctx.now)<=1e-9
                and 0<=p.observed_s<=p.submitted_s<=ctx.now+1e-9
                and 0<=p.wall_observed<=ctx.wall_started+1e-9 and p.wall_observed<=wall
                and ctx.now+self.delay-p.observed_s<self.cfg.proposal_ttl-1e-9
                and wall+self.delay-p.wall_observed<self.cfg.proposal_ttl-1e-9)
        except (ValueError,TypeError):return False

    def finish(self,ctx,proposal=None,deadline_wall=None):
        if ctx is not self._prepared:raise ValueError('only the current unfinished context may be finalized')
        if self._history_marker()!=self._prepared_history:
            raise RuntimeError('final ownership must precede physical application')
        if len(self.pending)!=ctx.pending_index+1 or self.pending[-1]!=(ctx.now+self.delay,Command(ctx.reference_first,ctx.acceleration)):
            raise RuntimeError('provisional analytical queue changed before final ownership')
        if deadline_wall is not None and not math.isfinite(deadline_wall):raise ValueError('finite deadline required')
        row=ctx.row;row.update(sequence_plan_selected=False,sequence_reason='absent',projection_scale=0.,
            anchor_reference_cost=float(np.mean([r[0] for r in ctx.reference_values])),anchor_features=list(ctx.anchor_features))
        selected=None;raw=None;response_sequence=None;self.last_plan_score=None
        try:
            if deadline_wall is not None and self.clock()>deadline_wall:row['sequence_reason']='deadline_fallback';return row
            if proposal is None:return row
            if isinstance(proposal,CorrectionProposal):
                try:proposal=replace(proposal,coefficients=tuple(float(x) for x in proposal.coefficients))
                except (ValueError,TypeError):row['sequence_reason']='invalid_or_expired';return row
            if not self._proposal_valid(ctx,proposal):row['sequence_reason']='invalid_or_expired';return row
            response_sequence=proposal.sequence
            # Copy caller-owned sequences before any numerical scoring.
            a=tuple(float(x) for x in proposal.coefficients)
            if not ctx.eligible:row['sequence_reason']='analytical_guard_or_safety_active';return row
            raw=self.score_candidate(ctx,a);self.last_plan_score=raw
            row.update(raw_score_values=[list(v) for v in raw.values],raw_score_violations=dict(raw.violations),
                raw_score_cost=raw.cost,raw_score_margin=raw.margin,sequence_coefficients=list(a),
                sequence_age=ctx.now+self.delay-proposal.observed_s,
                sequence_wall_age=self.clock()+self.delay-proposal.wall_observed)
            if deadline_wall is not None and self.clock()>deadline_wall:row['sequence_reason']='deadline_fallback';return row
            if not self._proposal_valid(ctx,proposal):row['sequence_reason']='expired_before_issue';return row
            if raw.neutral:row['sequence_reason']='neutral';return row
            reference=row['anchor_reference_cost']
            for scale in self.projection_scales:
                if deadline_wall is not None and self.clock()>deadline_wall:
                    row['sequence_reason']='deadline_fallback';return row
                if not self._proposal_valid(ctx,proposal):row['sequence_reason']='expired_before_issue';return row
                score=raw if scale==1. else self.score_candidate(ctx,a,scale)
                if deadline_wall is not None and self.clock()>deadline_wall:
                    row['sequence_reason']='deadline_fallback';return row
                if not self._proposal_valid(ctx,proposal):row['sequence_reason']='expired_before_issue';return row
                if score.admissible and score.cost<reference-1e-8:
                    selected=score;break
            if deadline_wall is not None and self.clock()>deadline_wall:row['sequence_reason']='deadline_fallback';return row
            if selected is None:row['sequence_reason']='guard_or_cost_rejected';return row
            if abs(selected.first-ctx.reference_first)<=1e-12:
                row['sequence_reason']='no_first_command_change';return row
            if deadline_wall is not None and self.clock()>deadline_wall:row['sequence_reason']='deadline_fallback';return row
            if not self._proposal_valid(ctx,proposal):row['sequence_reason']='expired_before_issue';return row
            command=Command(selected.first,ctx.acceleration)
            self.pending[ctx.pending_index]=(ctx.now+self.delay,command);self.issued=command
            row.update(source='ppo_anchor',sequence_plan_selected=True,sequence_reason='fresh_anchored_improvement',
                issued_steering=selected.first,projection_scale=selected.scale,sequence_cost=selected.cost,
                sequence_margin=selected.margin,applied_score_values=[list(v) for v in selected.values],
                planned_candidate_selected=False)
            row['residual']=float(np.clip(selected.first-self.baseline_fn(np.asarray(ctx.state),self.route),-self.cfg.residual_limit,self.cfg.residual_limit))
            row['costs']['ppo_anchor']=selected.cost;row['eligible']['ppo_anchor']=True
            return row
        finally:
            row['complete_decision_ms']=1000*max(0.,self.clock()-ctx.wall_started)
            if response_sequence is not None:self._proposal_sequence=response_sequence
            self._last_finished_history=self._prepared_history
            self._prepared=None;self._prepared_history=None;self._last_finished=ctx

    def restore_baseline(self,ctx,reason,row=None):
        """Final caller-side deadline/age rollback, before physical application."""
        if ctx is not self._last_finished or self._prepared is not None:
            raise ValueError('only the most recently finished context may be restored')
        if self._history_marker()!=self._last_finished_history:
            raise RuntimeError('analytical restoration must precede physical application')
        if len(self.pending)!=ctx.pending_index+1 or self.pending[ctx.pending_index][0]!=ctx.now+self.delay:
            raise RuntimeError('analytical restoration must precede physical application')
        command=Command(ctx.reference_first,ctx.acceleration)
        self.pending[ctx.pending_index]=(ctx.now+self.delay,command);self.issued=command
        restored=ctx.row
        if row is not None:
            for key,value in row.items():
                if key.startswith('raw_score_') or key in ('sequence_coefficients','sequence_age','sequence_wall_age'):
                    restored[key]=value
        restored.update(sequence_plan_selected=False,sequence_reason=str(reason),projection_scale=0.,
            anchor_reference_cost=float(np.mean([v[0] for v in ctx.reference_values])),
            anchor_features=list(ctx.anchor_features),complete_decision_ms=1000*max(0.,self.clock()-ctx.wall_started))
        return restored

    def decide(self,now,worker_failed=False):
        # Existing callers get the exact shared analytical/safety owner. New
        # current-tick neural callers explicitly use prepare/finish.
        if worker_failed:return super().decide(now,worker_failed=True)
        return self.finish(self.prepare(now))
