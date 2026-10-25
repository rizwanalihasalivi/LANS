"""Declared nominal constrained MPC reference; no hidden scenario parameters."""
from functools import lru_cache
import numpy as np
from scipy.linalg import expm,solve_discrete_are,block_diag
from scipy import sparse
import osqp

N=20;DT=.05;RATE=.35;TAU=.05


@lru_cache(maxsize=64)
def matrices(speed):
    v=speed;cf=cr=80000.;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0,1,v,0,0],[0,-(cf+cr)/(m*v),0,(cr*lr-cf*lf)/(m*v)-v,cf/m],
                [0,0,0,1,0],[0,(cr*lr-cf*lf)/(iz*v),0,-(cf*lf**2+cr*lr**2)/(iz*v),cf*lf/iz],
                [0,0,0,0,-1/TAU]])
    b=np.array([0,0,0,0,1/TAU]);e=np.array([0,0,-v,0,0])
    augmented=np.zeros((7,7));augmented[:5,:5]=a;augmented[:5,5]=b;augmented[:5,6]=e
    discrete=expm(augmented*DT);ad=discrete[:5,:5];bd=discrete[:5,5];ed=discrete[:5,6]
    sx=np.zeros((5*N,5));su=np.zeros((5*N,N));sk=np.zeros((5*N,N))
    for i in range(N):
        sx[5*i:5*i+5]=np.linalg.matrix_power(ad,i+1)
        for j in range(i+1):
            power=np.linalg.matrix_power(ad,i-j)
            su[5*i:5*i+5,j]=power@bd;sk[5*i:5*i+5,j]=power@ed
    q=np.diag([4.,.1,8.,.2,0.])*DT;r=100.*DT
    terminal=solve_discrete_are(ad,bd[:,None],q,np.array([[r]]))
    qbar=block_diag(*([q]*(N-1)+[q+terminal]))
    hessian=2*(su.T@qbar@su+r*np.eye(N))
    # delta BEFORE each control, so |u-delta|<=rate*tau bounds initial lag derivative.
    previous_u=np.vstack([np.zeros((1,N)),su[4::5][:-1]])
    constraints=sparse.csc_matrix(np.vstack([np.eye(N),np.eye(N)-previous_u,su[4::5]]))
    return sx,su,sk,qbar,r,sparse.csc_matrix(np.triu(hessian)),constraints


class MPC:
    def __init__(self):self.solvers={};self.calls=0;self.fallbacks=0;self.last_status='not_run'
    def command(self,estimate,actuator,speed,previews,baseline):
        self.calls+=1
        if not np.isfinite([*estimate,actuator,speed,*previews]).all():
            self.fallbacks+=1;self.last_status='invalid';return baseline
        v=float(np.round(max(5.,speed),1));sx,su,sk,qbar,r,p,am=matrices(v)
        state=np.array([*estimate,actuator])
        curvature=np.interp(v*DT*np.arange(1,N+1),[0,10,20],previews)
        free=sx@state+sk@curvature
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*v*v)*curvature
        vy=(1.4*v-1650*1.2*v**3/(2.6*80000))*curvature
        target=np.column_stack([np.zeros(N),vy,-vy/v,v*curvature,ff]).reshape(-1)
        gradient=2*(su.T@qbar@(free-target)-r*ff)
        previous_delta=np.r_[actuator,free[4::5][:-1]]
        lower=np.r_[np.full(N,-.5),previous_delta-RATE*TAU,-.5-free[4::5]]
        upper=np.r_[np.full(N,.5),previous_delta+RATE*TAU,.5-free[4::5]]
        if v not in self.solvers:
            solver=osqp.OSQP();solver.setup(P=p,q=gradient,A=am,l=lower,u=upper,
                verbose=False,eps_abs=1e-5,eps_rel=1e-5,max_iter=3000,warm_start=True,polish=False)
            self.solvers[v]=solver
        else:
            solver=self.solvers[v];solver.update(q=gradient,l=lower,u=upper)
        result=solver.solve();self.last_status=result.info.status
        if result.info.status_val not in (1,2) or result.x is None or not np.isfinite(result.x).all():
            self.fallbacks+=1;return baseline
        constraint=am@result.x
        if max(float(np.max(lower-constraint)),float(np.max(constraint-upper)))>1e-4:
            self.fallbacks+=1;self.last_status='constraint_violation';return baseline
        return float(np.clip(result.x[0],-.5,.5))
