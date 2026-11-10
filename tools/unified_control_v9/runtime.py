"""Causal asynchronous conic proposals; robust admission stays in the owner.

The logical backend models a fixed service time and makes no wall-time claim.
The process backend never waits for a solver during a control tick. Startup and
close may wait and must happen outside measured control ticks.
"""
from dataclasses import dataclass
from queue import Empty,Full
from types import SimpleNamespace
import math,multiprocessing as mp,time
import numpy as np
from integrations.unified_lans.physics import Config,Command,constrain
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v4.kernels import geometry
from tools.unified_control_v5.control import baseline_plan,project
from tools.unified_control_v7.control import Planner as ConicPlanner
from tools.unified_control_v8.control import Controller as Previous


@dataclass(frozen=True)
class Request:
    sequence:int
    observed_s:float
    submitted_s:float
    application_s:float
    wall_submitted:float
    state:tuple
    previous:float
    accel:float
    cfg:Config
    stiffness:float
    feedback:float
    gains:tuple
    route:tuple
    vehicles:tuple
    factor:float

    @property
    def key(self):
        return (self.sequence,self.observed_s,self.submitted_s,self.application_s,self.wall_submitted)


@dataclass(frozen=True)
class Response:
    key:tuple
    status:str
    commands:tuple|None
    solve_wall_ms:float


class _FrozenSupervisor:
    def __init__(self,request):
        self.state='SAFE';self.request=request
    def assess(self,*args):
        return SimpleNamespace(vehicles=tuple((name,np.asarray(state),unc) for name,state,unc in self.request.vehicles))
    def acceleration(self,*args):return self.request.accel


class _FrozenRoute:
    def __init__(self,parameters):self.parameters=parameters
    def geometry(self,x):
        r=self.parameters
        return geometry(x,int(r[0]),r[1],r[2],r[3])


def solve_request(request):
    """Only serialized received/estimated data enter the original conic solver."""
    started=time.perf_counter()
    owner=SimpleNamespace(supervisor=_FrozenSupervisor(request),inbox=None,expected=(),
        _decision_now=request.submitted_s,delay=request.application_s-request.submitted_s,
        target_speed=request.state[3],adaptive=True,stiffness_estimate=request.stiffness,
        _gains=np.asarray(request.gains),_route=np.asarray(request.route),feedback_stiffness=request.feedback)
    planner=ConicPlanner(owner,request.factor)
    commands=planner.plan(np.asarray(request.state),_FrozenRoute(request.route),request.previous,
                          request.cfg,request.feedback,16.)
    return Response(request.key,planner.status,None if commands is None else tuple(float(x) for x in commands),
                    1000*(time.perf_counter()-started))


def _process(incoming,outgoing,cfg,factor,stall_s):
    try:
        warm=Request(0,0.,0.,0.,0.,(0.,.3,0.,12.,0.,0.),0.,0.,cfg,1.,1.,
            tuple(tuple(float(x) for x in row) for row in gain_table(16.,1.)),(0.,1.,0.,1.),(),factor)
        solve_request(warm)
        outgoing.put(('ready',None))
        while True:
            request=incoming.get()
            if request is None:return
            response=solve_request(request)
            if stall_s:time.sleep(stall_s)
            outgoing.put(('response',response))
    except Exception as exc:
        outgoing.put(('error',type(exc).__name__+': '+str(exc)))


class LogicalPlanner:
    """Deterministic one-request logical service; synchronous solve is simulation only."""
    def __init__(self,service_s=.05,solver=solve_request):
        if not math.isfinite(service_s) or service_s<=0:raise ValueError('positive service required')
        self.service_s=service_s;self.solver=solver;self.pending=None;self.failed=False;self.error='';self.ready=True
    @property
    def busy(self):return self.pending is not None
    def submit(self,request,now):
        if self.busy or self.failed:return False
        self.pending=(now+self.service_s,request,self.solver(request));return True
    def poll(self,now):
        if self.pending is None or self.pending[0]>now+1e-9:return None
        _,request,response=self.pending;self.pending=None
        if response.key!=request.key:
            self.failed=True;self.error='response identity mismatch';return None
        return request,response
    def close(self):self.pending=None;self.ready=False


class AsyncPlanner:
    """Bounded spawned solver; only startup/close use blocking waits."""
    def __init__(self,cfg,factor=1.10,stall_s=0.):
        if not math.isfinite(stall_s) or stall_s<0:raise ValueError('nonnegative stall required')
        context=mp.get_context('spawn');self.incoming=context.Queue(maxsize=1);self.outgoing=context.Queue(maxsize=2)
        self.process=context.Process(target=_process,args=(self.incoming,self.outgoing,cfg,factor,stall_s),daemon=True)
        self.pending=None;self.failed=False;self.error='';self.ready=False;self.closed=False
        self.process.start()
        try:
            kind,payload=self.outgoing.get(timeout=60.)
            if kind!='ready':raise RuntimeError(str(payload))
            self.ready=True
        except Exception:
            self.close();raise
    @property
    def busy(self):return self.pending is not None
    def submit(self,request,now):
        if self.closed or self.busy or self.failed:return False
        if not self.process.is_alive():self.failed=True;self.error='solver exited';return False
        try:self.incoming.put_nowait(request)
        except Full:return False
        self.pending=request;return True
    def poll(self,now):
        if self.closed:return None
        try:kind,payload=self.outgoing.get_nowait()
        except Empty:
            if not self.process.is_alive():self.failed=True;self.error='solver exited'
            return None
        request=self.pending;self.pending=None
        if kind!='response' or request is None or not isinstance(payload,Response) or payload.key!=request.key:
            self.failed=True;self.error=str(payload) if kind=='error' else 'response identity mismatch';return None
        return request,payload
    def close(self):
        if self.closed:return
        self.closed=True;self.ready=False
        if self.process.is_alive():
            try:self.incoming.put_nowait(None)
            except Full:pass
            self.process.join(timeout=1.)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=2.)
        else:self.process.join(timeout=1.)
        for queue in (self.incoming,self.outgoing):queue.cancel_join_thread();queue.close()


class ProposalPlanner:
    def __init__(self,owner,backend,factor,ttl_s,process_mode):
        self.owner=owner;self.backend=backend;self.factor=factor;self.ttl_s=ttl_s;self.process_mode=process_mode
        self.sequence=0;self.calls=0;self.failures=0;self.accepted=0;self.rejected=0;self.status='NOT_RUN'
        self.candidate=None;self.used_request=None;self.shift=None;self.reason='not_available'
    def wall(self):return time.monotonic() if self.process_mode else self.owner._decision_now
    def fresh(self,request,now,wall):
        age=now+self.owner.delay-request.observed_s;wall_age=wall+self.owner.delay-request.wall_submitted
        return (0<=age<self.ttl_s-1e-9 and 0<=wall_age<self.ttl_s-1e-9
                and now+1e-9>=request.submitted_s)
    def plan(self,state,route,previous,cfg,stiffness,penalty):
        c=self.owner;now=c._decision_now;wall=self.wall();self.calls+=1;self.used_request=None;self.shift=None
        reply=self.backend.poll(now)
        if reply is not None:
            request,response=reply
            valid=(response.key==request.key and response.status=='Solved' and response.commands is not None
                   and len(response.commands)==round(cfg.horizon/cfg.dt) and np.isfinite(response.commands).all()
                   and self.fresh(request,now,wall))
            if valid:self.candidate=reply;self.accepted+=1
            else:self.rejected+=1;self.failures+=1;self.reason='invalid_or_expired_response'
        old=c.supervisor.state
        risk=c.supervisor.assess(state,c.inbox,c.expected,now,now+c.delay);c.supervisor.state=old
        accel=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-state[3]),-cfg.max_brake,cfg.max_accel)),risk)
        center=c.stiffness_estimate if c.adaptive else 1.
        if not self.backend.busy and not self.backend.failed:
            packet=c.inbox.latest.get('ego')
            if packet is not None:
                request=Request(self.sequence+1,float(packet.observed_s),now,now+c.delay,wall,
                    tuple(float(x) for x in state),float(previous),float(accel),cfg,float(center),float(c.feedback_stiffness),
                    tuple(tuple(float(x) for x in row) for row in c._gains),tuple(float(x) for x in c._route),
                    tuple((name,tuple(float(x) for x in other),float(unc)) for name,other,unc in risk.vehicles),self.factor)
                if self.backend.submit(request,now):self.sequence+=1
        if self.backend.failed:
            self.status='WORKER_FAILED';self.reason=self.backend.error;return None
        if self.candidate is None:
            self.status='PENDING';return None
        request,response=self.candidate
        if not self.fresh(request,now,self.wall()):
            self.candidate=None;self.status='EXPIRED';self.reason='candidate_expired';return None
        elapsed=(now+c.delay-request.application_s)/cfg.dt;shift=round(elapsed)
        if abs(elapsed-shift)>1e-7 or not 0<=shift<len(response.commands):
            self.candidate=None;self.status='MISALIGNED';self.reason='application_grid_mismatch';return None
        n=round(cfg.horizon/cfg.dt)
        plan=baseline_plan(state,n,accel,previous,cfg.dt,center,c._gains,c._route,
                           cfg.steering_limit,cfg.steering_rate,c.feedback_stiffness)
        remaining=np.asarray(response.commands[shift:]);plan[:len(remaining)]=remaining
        plan=project(state,plan,accel,previous,cfg.dt,center,c._gains,c._route,
                     cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,c.feedback_stiffness)
        self.used_request=request;self.shift=shift;self.status='Solved';self.reason='fresh_projected_proposal'
        return plan
    def close(self):self.backend.close()


class RuntimeController(Previous):
    def __init__(self,*args,planner_backend='logical',planner_service_s=.05,planner_wall_stall_s=0.,planner_ttl_s=.15,**kwargs):
        if planner_backend not in ('logical','process'):raise ValueError('unknown planner backend')
        if not math.isfinite(planner_ttl_s) or not 0<planner_ttl_s<=.15:raise ValueError('planner TTL must be <=150ms')
        super().__init__(*args,**kwargs)
        self.planner_backend=planner_backend
        if self.planner is not None:
            factor=self.planner.factor
            backend=(LogicalPlanner(planner_service_s) if planner_backend=='logical' else
                     AsyncPlanner(self.cfg,factor,planner_wall_stall_s))
            self.planner=ProposalPlanner(self,backend,factor,planner_ttl_s,planner_backend=='process')
    def decide(self,now,worker_failed=False):
        start=time.perf_counter();previous=self.issued;result=super().decide(now,worker_failed)
        if self.planner is not None:
            planner=self.planner;request=planner.used_request
            if result['planned_candidate_selected'] and request is not None and not planner.fresh(request,now,planner.wall()):
                state=self.forecast(now)
                steering=self.baseline_fn(state,self.route) if state is not None else previous.steering
                accel=result['issued_accel'] if result['eligible'].get('lqr',False) else -self.cfg.max_brake
                command=constrain(Command(steering,accel),previous,self.cfg)
                self.pending[-1]=(now+self.delay,command);self.issued=command
                result.update(source='lqr',residual=0.,reason='planner_expired_before_issue',
                    issued_steering=command.steering,issued_accel=command.accel,planned_candidate_selected=False)
            selected=result['planned_candidate_selected']
            result.update(planner_backend=self.planner_backend,planner_busy=planner.backend.busy,
                planner_worker_failed=planner.backend.failed,planner_response_accepted=planner.accepted,
                planner_response_rejected=planner.rejected,planner_proposal_reason=planner.reason,
                planner_used_request=request.sequence if request is not None and selected else None,
                planner_proposal_age=now+self.delay-request.observed_s if request is not None else None,
                planner_proposal_wall_age=planner.wall()+self.delay-request.wall_submitted if request is not None else None,
                planner_shift=planner.shift)
        result['complete_decision_ms']=1000*(time.perf_counter()-start)
        return result
    def close(self):
        if self.planner is not None:self.planner.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
