"""Typed sequence proposals compete with unchanged v8 analytical decisions."""
from dataclasses import dataclass
import math,time
import numpy as np
from numba import njit
from integrations.unified_lans.physics import Command
from tools.unified_control_v4.kernels import lqr,step
from tools.unified_control_v8.control import Controller as Base


@dataclass(frozen=True)
class PlanProposal:
    sequence:int
    observed_s:float
    submitted_s:float
    wall_observed:float
    knots:tuple


@njit(cache=True)
def commands(state,knots,shift,accel,previous,cfg_dt,n,center,gains,route,feedback):
    z=state.copy();result=np.zeros(n)
    for i in range(n):
        where=(i+shift)*7/max(1,n-1);residual=0.
        if where<=7:
            lower=int(math.floor(where));upper=min(7,lower+1);fraction=where-lower
            residual=.08*((1-fraction)*knots[lower]+fraction*knots[upper])
        base=lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback)
        u=min(.5,max(-.5,min(previous+.6*cfg_dt,max(previous-.6*cfg_dt,base+residual))))
        result[i]=u;z=step(z,u,accel,cfg_dt,center);previous=u
    return result


class Controller(Base):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.plan_proposal=None;self.plan_sequence=-1
        if (self.cfg.steering_limit,self.cfg.steering_rate,self.cfg.residual_limit,self.cfg.proposal_ttl,self.cfg.horizon)!=(.5,.6,.08,.15,2.):
            raise ValueError('This declared proposal contract requires the original physical and freshness limits')
    def accept_plan(self,proposal,now):
        wall=self.clock()
        if not isinstance(proposal,PlanProposal):return False
        try:
            knots=np.asarray(proposal.knots,dtype=float)
            finite=knots.shape==(8,) and np.isfinite(knots).all() and np.isfinite([proposal.observed_s,proposal.submitted_s,proposal.wall_observed,now,wall]).all()
        except (ValueError,TypeError):return False
        valid=(finite and type(proposal.sequence) is int and proposal.sequence>self.plan_sequence
            and max(abs(x) for x in proposal.knots)<=1.+1e-12
            and 0<=proposal.observed_s<=proposal.submitted_s<=now+1e-9
            and 0<=wall-proposal.wall_observed and now+self.delay-proposal.observed_s<=.15+1e-9
            and wall+self.delay-proposal.wall_observed<=.15+1e-9)
        if valid:self.plan_proposal=proposal;self.plan_sequence=proposal.sequence
        return valid
    def fresh_plan(self,now):
        p=self.plan_proposal
        return (p is not None and now+self.delay-p.observed_s<.15-1e-9
            and 0<=self.clock()-p.wall_observed and self.clock()+self.delay-p.wall_observed<.15-1e-9)
    def score_plan(self,z,knots,shift,accel,previous,vehicles):
        saved=(self.issued,self._plan,self._plan_residual,self._cost_reference)
        try:
            self.issued=previous;self._cost_reference=None
            plan=commands(z,np.asarray(knots,float),shift,accel,previous.steering,self.cfg.dt,
                round(self.cfg.horizon/self.cfg.dt),self.stiffness_estimate,self._gains,self._route,self.feedback_stiffness)
            residual=float(np.clip(plan[0]-self.baseline_fn(z,self.route),-.08,.08))
            self._plan=plan;self._plan_residual=residual
            value,margin=self.cost(z.copy(),Command(float(plan[0]),accel),residual,accel,vehicles,.05)
            return value,margin,plan,residual
        finally:self.issued,self._plan,self._plan_residual,self._cost_reference=saved
    def decide(self,now,worker_failed=False):
        start=time.perf_counter();previous=self.issued;decision=super().decide(now,worker_failed)
        decision.update(sequence_plan_selected=False,sequence_age=None,sequence_wall_age=None,sequence_reason='absent_or_expired')
        if not self.fresh_plan(now) or worker_failed or decision['ego_backup'] or decision['risk']=='DANGER':return decision
        if not decision['eligible'].get(decision['source'],False):return decision
        z=self.forecast(now)
        if z is None:return decision
        old=self.supervisor.state;risk=self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay);self.supervisor.state=old
        p=self.plan_proposal;elapsed=(now-p.submitted_s-.05)/self.cfg.dt;shift=round(elapsed)
        if abs(elapsed-shift)>1e-8 or not 0<=shift<round(self.cfg.horizon/self.cfg.dt):return decision
        value,margin,plan,residual=self.score_plan(z,p.knots,shift,decision['issued_accel'],previous,risk.vehicles)
        reference=decision['costs'][decision['source']]
        decision.update(sequence_cost=value,sequence_margin=margin,sequence_reference_cost=reference,
            sequence_age=now+self.delay-p.observed_s,sequence_wall_age=self.clock()+self.delay-p.wall_observed,
            sequence_knots=list(p.knots),sequence_shift=shift,sequence_reason='guard_or_cost_rejected')
        if margin>=0 and value<reference-1e-8 and self.fresh_plan(now):
            command=Command(float(plan[0]),decision['issued_accel']);self.pending[-1]=(now+self.delay,command);self.issued=command
            decision.update(source='ppo_plan',residual=residual,issued_steering=command.steering,
                sequence_plan_selected=True,planned_candidate_selected=False,sequence_reason='fresh_robust_improvement')
        decision['complete_decision_ms']=1000*(time.perf_counter()-start)
        return decision
