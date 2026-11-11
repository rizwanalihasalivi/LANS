"""Received-data-only conic planning against the fixed nominal R16 reference.

All model points share one open-loop command vector. Nonlinear owner admission
still checks the issued proposal; this linearization is not a safety certificate.
"""
from dataclasses import dataclass
import multiprocessing as mp
import time
import numpy as np
from scipy import sparse
import clarabel
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v5.control import baseline_plan,project
from tools.unified_control_v7.control import trace,linearized_prediction
from tools.unified_control_v9.runtime import Request as PriorRequest,Response,LogicalPlanner,AsyncPlanner
from .pareto_kernels import rollout


@dataclass(frozen=True)
class Request(PriorRequest):
    uncertainty:float=.3


def solve(request):
    start_time=time.perf_counter();r=request;cfg=r.cfg;n=round(cfg.horizon/cfg.dt)
    z=np.asarray(r.state);gains=np.asarray(r.gains);route=np.asarray(r.route)
    models=(max(.7,r.stiffness-r.uncertainty),r.stiffness,min(1.3,r.stiffness+r.uncertainty))
    seed=baseline_plan(z,n,r.accel,r.previous,cfg.dt,r.stiffness,gains,route,cfg.steering_limit,cfg.steering_rate,1.)
    d=np.eye(n);d[np.arange(1,n),np.arange(n-1)]=-1.;start=np.r_[r.previous,np.zeros(n-1)]
    matrices=[np.eye(n),-np.eye(n),d,-d];bounds=[np.full(n,cfg.steering_limit),np.full(n,cfg.steering_limit),start+cfg.steering_rate*cfg.dt,-start+cfg.steering_rate*cfg.dt]
    cone_blocks=[];cone_bounds=[];objectives=[];offsets=[]
    for stiffness in models:
        states=trace(z,seed,r.accel,cfg.dt,stiffness)
        ef,em,hf,hm,positions,position_matrices,residual,offset,mask=linearized_prediction(z,states,seed,r.accel,stiffness,gains,route,1.)
        matrices.extend([em,-em]);bounds.extend([np.full(n,1.75-1e-8)-ef,np.full(n,1.75-1e-8)+ef])
        if mask.any():matrices.extend([residual[mask],-residual[mask]]);bounds.extend([offset[mask]+cfg.residual_limit,-offset[mask]+cfg.residual_limit])
        for _,other,unc in r.vehicles:
            other=np.asarray(other);vx=other[3]*np.cos(other[2])-other[4]*np.sin(other[2]);vy=other[3]*np.sin(other[2])+other[4]*np.cos(other[2])
            for i in range(n):
                future=other[:2]+np.array([vx,vy])*(i+1)*cfg.dt;v=states[i,:2]-future;normal=v/max(1e-12,np.linalg.norm(v))
                radius=2*cfg.vehicle_radius+cfg.buffer+unc+cfg.uncertainty_rate*(i+1)*cfg.dt
                matrices.append((-normal@position_matrices[i])[None,:]);bounds.append(np.array([normal@(positions[i]-future)-radius]))
        # Reference is a separate closed-loop rollout, not the optimized seed's
        # quality. The same physical model point is used on both sides.
        reference=rollout(z,seed[0],r.accel,r.previous,cfg.dt,cfg.horizon,stiffness,gains,route,np.empty((0,7)),cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,1.,None)
        hcap=np.sqrt(max(0.,r.factor*r.factor*reference[2]/cfg.dt))
        rcap=np.sqrt(max(0.,r.factor*r.factor*reference[3]/cfg.dt))
        cone_blocks.extend([sparse.csc_matrix(np.vstack([np.zeros(n),-hm])),sparse.csc_matrix(np.vstack([np.zeros(n),-d/cfg.dt]))])
        cone_bounds.extend([np.r_[hcap,hf],np.r_[rcap,-start/cfg.dt]])
        objectives.append(em);offsets.append(ef)
    a=sparse.csc_matrix(np.vstack(matrices));b=np.concatenate(bounds);cones=[clarabel.NonnegativeConeT(len(b))]
    cones.extend(clarabel.SecondOrderConeT(n+1) for _ in cone_blocks)
    em=np.vstack(objectives);ef=np.concatenate(offsets);scale=max(1e-6,float(np.sum((ef+em@seed)**2)))
    p=sparse.csc_matrix(np.triu(2*em.T@em/scale+1e-8*np.eye(n)));q=2*em.T@ef/scale
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_iter=80
    settings.tol_feas=1e-8;settings.tol_gap_abs=1e-8;settings.tol_gap_rel=1e-8
    solution=clarabel.DefaultSolver(p,q,sparse.vstack([a,*cone_blocks],format='csc'),np.concatenate([b,*cone_bounds]),cones,settings).solve()
    status=str(solution.status);commands=None
    if status=='Solved' and solution.x is not None and np.isfinite(solution.x).all():
        commands=project(z,np.asarray(solution.x),r.accel,r.previous,cfg.dt,r.stiffness,gains,route,cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,1.)
        commands=tuple(float(x) for x in commands)
    return Response(r.key,status,commands,1000*(time.perf_counter()-start_time))


def worker(incoming,outgoing,cfg,factor,stall_s):
    try:
        warm=Request(0,0.,0.,0.,0.,(0.,.3,0.,12.,0.,0.),0.,0.,cfg,1.,1.,tuple(tuple(float(x) for x in row) for row in gain_table(16.,1.)),(0.,1.,0.,1.),(),factor,.3)
        solve(warm);outgoing.put(('ready',None))
        while True:
            request=incoming.get()
            if request is None:return
            response=solve(request)
            if stall_s:time.sleep(stall_s)
            outgoing.put(('response',response))
    except Exception as exc:outgoing.put(('error',type(exc).__name__+': '+str(exc)))


class Logical(LogicalPlanner):
    def __init__(self,owner,service_s):
        self.owner=owner;super().__init__(service_s,self.solve)
    def solve(self,r):return solve(Request(**vars(r),uncertainty=self.owner.stiffness_uncertainty if self.owner.adaptive else .3))


class Process(AsyncPlanner):
    def __init__(self,owner,cfg,factor,stall_s=0.):
        self.owner=owner;context=mp.get_context('spawn');self.incoming=context.Queue(maxsize=1);self.outgoing=context.Queue(maxsize=2)
        self.process=context.Process(target=worker,args=(self.incoming,self.outgoing,cfg,factor,stall_s),daemon=True)
        self.pending=None;self.failed=False;self.error='';self.ready=False;self.closed=False;self.process.start()
        try:
            kind,payload=self.outgoing.get(timeout=60.)
            if kind!='ready':raise RuntimeError(str(payload))
            self.ready=True
        except Exception:self.close();raise
    def submit(self,r,now):return super().submit(Request(**vars(r),uncertainty=self.owner.stiffness_uncertainty if self.owner.adaptive else .3),now)
