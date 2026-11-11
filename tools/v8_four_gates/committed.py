"""Submit after command issue and plan beyond its committed service prefix.

An asynchronous solver must not assume its still-unavailable first action was
applied during its service interval. Observation and wall freshness keep their
original clocks; predicted states never count as new measurements.
"""
import numpy as np
import time
from tools.unified_control_v5.control import baseline_plan,project
from tools.unified_control_v9.runtime import ProposalPlanner,Request
from .robust_control import Controller as Parent


class Planner(ProposalPlanner):
    def plan(self,state,route,previous,cfg,stiffness,penalty):
        c=self.owner;now=c._decision_now;self.calls+=1;self.used_request=None;self.shift=None
        reply=self.backend.poll(now)
        if reply is not None:
            request,response=reply
            valid=(response.key==request.key and response.status=='Solved' and response.commands is not None
                   and len(response.commands)==round(cfg.horizon/cfg.dt) and np.isfinite(response.commands).all()
                   and self.fresh(request,now,self.wall()))
            if valid:self.candidate=reply;self.accepted+=1
            else:self.rejected+=1;self.failures+=1;self.reason='invalid_or_expired_response'
        if self.backend.failed:self.status='WORKER_FAILED';self.reason=self.backend.error;return None
        if self.candidate is None:self.status='PENDING';return None
        request,response=self.candidate
        if not self.fresh(request,now,self.wall()):
            self.candidate=None;self.status='EXPIRED';self.reason='candidate_expired';return None
        elapsed=(now+c.delay-request.application_s)/cfg.dt;shift=round(elapsed)
        if abs(elapsed-shift)>1e-7 or not 0<=shift<len(response.commands):
            self.status='MISALIGNED';self.reason='application_grid_mismatch';return None
        center=c.stiffness_estimate if c.adaptive else 1.;n=round(cfg.horizon/cfg.dt)
        # The first command has already been issued before submission. Its
        # acceleration is the request's prediction assumption, never plant truth.
        plan=baseline_plan(state,n,request.accel,previous,cfg.dt,center,c._gains,c._route,cfg.steering_limit,cfg.steering_rate,c.feedback_stiffness)
        remaining=np.asarray(response.commands[shift:]);plan[:len(remaining)]=remaining
        plan=project(state,plan,request.accel,previous,cfg.dt,center,c._gains,c._route,cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,c.feedback_stiffness)
        self.used_request=request;self.shift=shift;self.status='Solved';self.reason='fresh_committed_prefix_proposal';return plan

    def submit_after_issue(self,now):
        c=self.owner;packet=c.inbox.latest.get('ego')
        if self.backend.busy or self.backend.failed or packet is None or now-packet.observed_s>c.cfg.ego_ttl+1e-9:return False
        state=c.forecast(now)
        if state is None or c.supervisor.force_stop:return False
        service=c.cfg.dt;application=now+c.delay+service
        # forecast(now) includes the whole existing actuator FIFO through
        # now+delay; continue with the just-issued command for one service tick.
        state=c.predict(state,c.issued,service)
        old=c.supervisor.state;risk=c.supervisor.assess(state,c.inbox,c.expected,now,application);c.supervisor.state=old
        if risk.missing or risk.state=='DANGER':return False
        center=c.stiffness_estimate if c.adaptive else 1.
        request=Request(self.sequence+1,float(packet.observed_s),now,application,self.wall(),
            tuple(float(x) for x in state),float(c.issued.steering),float(c.issued.accel),c.cfg,float(center),float(c.feedback_stiffness),
            tuple(tuple(float(x) for x in row) for row in c._gains),tuple(float(x) for x in c._route),
            tuple((name,tuple(float(x) for x in other),float(unc)) for name,other,unc in risk.vehicles),self.factor)
        submitted=self.backend.submit(request,now)
        if submitted:self.sequence+=1
        return submitted


class Controller(Parent):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        if self.planner is not None:
            p=self.planner;self.planner=Planner(self,p.backend,p.factor,p.ttl_s,p.process_mode)
    def decide(self,now,worker_failed=False):
        started=time.perf_counter()
        result=super().decide(now,worker_failed)
        submitted=False
        if self.planner is not None and not worker_failed:submitted=self.planner.submit_after_issue(now)
        result.update(planner_committed_prefix=True,planner_submitted_after_issue=submitted,planner_busy=self.planner.backend.busy if self.planner else False)
        result['complete_decision_ms']=1000*(time.perf_counter()-started)
        return result
