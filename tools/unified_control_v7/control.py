"""Causal tracking-first conic proposal with existing robust nonlinear admission."""
import math,time
import numpy as np
from scipy import sparse
import clarabel
from numba import njit
from integrations.unified_lans.physics import Command
from tools.unified_control_v4.control import Controller as Previous
from tools.unified_control_v4.kernels import step,lqr,geometry
from tools.unified_control_v5.control import baseline_plan,project


@njit(cache=True)
def linearized_prediction(initial,states,commands,accel,stiff,gains,route,feedback):
    n=len(commands);free=initial.copy();su=np.zeros((6,n));before=initial.copy()
    ef=np.zeros(n);em=np.zeros((n,n));hf=np.zeros(n);hm=np.zeros((n,n))
    positions=np.zeros((n,2));position_matrices=np.zeros((n,2,n))
    residual=np.zeros((n,n));offset=np.zeros(n);mask=np.zeros(n,np.bool_)
    for i in range(n):
        previous_free=free.copy();previous_su=su.copy();u=commands[i];after=states[i];eps=1e-5
        a=np.zeros((6,6))
        for j in range(6):
            direction=np.zeros(6);direction[j]=eps
            a[:,j]=(step(before+direction,u,accel,.05,stiff)-step(before-direction,u,accel,.05,stiff))/(2*eps)
        b=(step(before,u+eps,accel,.05,stiff)-step(before,u-eps,accel,.05,stiff))/(2*eps)
        free=a@free+(after-a@before-b*u);su=a@su;su[:,i]+=b
        y,h,k=geometry(after[0],int(route[0]),route[1],route[2],route[3])
        dy=np.zeros(6);dy[0]=-math.tan(h);dy[1]=1.
        dh=np.zeros(6);dh[0]=-k/math.cos(h);dh[2]=1.
        ef[i]=after[1]-y+dy@(free-after);em[i]=dy@su
        hf[i]=math.atan2(math.sin(after[2]-h),math.cos(after[2]-h))+dh@(free-after);hm[i]=dh@su
        positions[i]=free[:2];position_matrices[i]=su[:2]
        base=lqr(before,gains,int(route[0]),route[1],route[2],route[3],feedback)
        if abs(u-base)<=.08+1e-8:
            grad=np.zeros(6)
            for j in (0,1,2,4,5):
                direction=np.zeros(6);direction[j]=eps
                grad[j]=(lqr(before+direction,gains,int(route[0]),route[1],route[2],route[3],feedback)-
                         lqr(before-direction,gains,int(route[0]),route[1],route[2],route[3],feedback))/(2*eps)
            residual[i]=-grad@previous_su;residual[i,i]+=1.
            offset[i]=base+grad@(previous_free-before);mask[i]=True
        before=after
    return ef,em,hf,hm,positions,position_matrices,residual,offset,mask


@njit(cache=True)
def trace(initial,commands,accel,dt,stiff):
    states=np.zeros((len(commands),6));state=initial.copy()
    for i in range(len(commands)):state=step(state,commands[i],accel,dt,stiff);states[i]=state
    return states


class Planner:
    def __init__(self,owner,factor):self.owner=owner;self.factor=factor;self.status='NOT_RUN';self.failures=0;self.calls=0
    def plan(self,state,route,previous,cfg,stiffness,penalty):
        if state[3]<2.:return None
        self.calls+=1;c=self.owner;n=round(cfg.horizon/cfg.dt);old=c.supervisor.state
        risk=c.supervisor.assess(state,c.inbox,c.expected,c._decision_now,c._decision_now+c.delay);c.supervisor.state=old
        accel=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-state[3]),-cfg.max_brake,cfg.max_accel)),risk)
        center=c.stiffness_estimate if c.adaptive else 1.
        seed=baseline_plan(state,n,accel,previous,cfg.dt,center,c._gains,c._route,cfg.steering_limit,cfg.steering_rate,c.feedback_stiffness)
        states=trace(state,seed,accel,cfg.dt,center)
        ef,em,hf,hm,positions,position_matrices,residual,offset,mask=linearized_prediction(state,states,seed,accel,center,c._gains,c._route,c.feedback_stiffness)
        d=np.eye(n);d[np.arange(1,n),np.arange(n-1)]=-1.
        start=np.r_[previous,np.zeros(n-1)];rate=cfg.steering_rate*cfg.dt
        matrices=[np.eye(n),-np.eye(n),d,-d,em,-em]
        bounds=[np.full(n,cfg.steering_limit),np.full(n,cfg.steering_limit),start+rate,-start+rate,
                np.full(n,1.75-1e-8)-ef,np.full(n,1.75-1e-8)+ef]
        if mask.any():matrices.extend([residual[mask],-residual[mask]]);bounds.extend([offset[mask]+cfg.residual_limit,-offset[mask]+cfg.residual_limit])
        for _,other,unc in risk.vehicles:
            vx=other[3]*math.cos(other[2])-other[4]*math.sin(other[2]);vy=other[3]*math.sin(other[2])+other[4]*math.cos(other[2])
            for i in range(n):
                future=other[:2]+np.array([vx,vy])*(i+1)*cfg.dt;v=states[i,:2]-future;normal=v/max(1e-12,np.linalg.norm(v))
                radius=2*cfg.vehicle_radius+cfg.buffer+unc+cfg.uncertainty_rate*(i+1)*cfg.dt
                matrices.append((-normal@position_matrices[i])[None,:]);bounds.append(np.array([normal@(positions[i]-future)-radius]))
        a=sparse.csc_matrix(np.vstack(matrices));b=np.concatenate(bounds);cones=[clarabel.NonnegativeConeT(len(b))]
        heading_reference=[]
        for z in states:
            _,h,_=route.geometry(z[0]);heading_reference.append(math.atan2(math.sin(z[2]-h),math.cos(z[2]-h)))
        hcap=math.sqrt(self.factor**2*np.sum(np.square(heading_reference))+2e-6/cfg.dt)
        rcap=math.sqrt(self.factor**2*np.sum(np.square((d@seed-start)/cfg.dt))+1e-5/cfg.dt)
        blocks=[a,sparse.csc_matrix(np.vstack([np.zeros(n),-hm])),sparse.csc_matrix(np.vstack([np.zeros(n),-d/cfg.dt]))]
        rhs=np.r_[b,hcap,hf,rcap,-start/cfg.dt]
        cones.extend([clarabel.SecondOrderConeT(n+1),clarabel.SecondOrderConeT(n+1)])
        scale=max(1e-6,float(np.sum((ef+em@seed)**2)))
        p=sparse.csc_matrix(np.triu(2*em.T@em/scale+1e-8*np.eye(n)));q=2*em.T@ef/scale
        settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_iter=60
        settings.tol_feas=1e-7;settings.tol_gap_abs=1e-7;settings.tol_gap_rel=1e-7
        solution=clarabel.DefaultSolver(p,q,sparse.vstack(blocks,format='csc'),rhs,cones,settings).solve()
        self.status=str(solution.status)
        if self.status!='Solved' or solution.x is None or not np.isfinite(solution.x).all():self.failures+=1;return None
        return project(state,np.asarray(solution.x),accel,previous,cfg.dt,center,c._gains,c._route,
                       cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,c.feedback_stiffness)


class Controller(Previous):
    def __init__(self,*args,quality_factor=1.10,**kwargs):
        super().__init__(*args,**kwargs);self._decision_now=0.
        if abs(self.cfg.dt-.05)>1e-12 or not 1.<=quality_factor<=1.10:
            raise ValueError('v7 requires 50 ms sampling and a predicted quality factor in [1,1.10]')
        if self.planner is not None:self.planner=Planner(self,quality_factor)
    def decide(self,now,worker_failed=False):
        self._decision_now=now;started=time.perf_counter();result=super().decide(now,worker_failed)
        result['complete_decision_ms']=1000*(time.perf_counter()-started)
        return result
