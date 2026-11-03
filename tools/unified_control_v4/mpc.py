"""Rate/residual-constrained predictive correction; no simulator-truth access."""
from functools import lru_cache
import numpy as np
from scipy.linalg import expm,solve_discrete_are,block_diag
from scipy import sparse
import osqp
from .control import gain


@lru_cache(maxsize=256)
def matrices(speed,stiffness,penalty,dt,n):
    v=max(2.,speed);cf=cr=80000*stiffness;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0.,1.,v,0.],[0.,-(cf+cr)/(m*v),0.,(cr*lr-cf*lf)/(m*v)-v],
                [0.,0.,0.,1.],[0.,(cr*lr-cf*lf)/(iz*v),0.,-(lf*lf*cf+lr*lr*cr)/(iz*v)]])
    b=np.array([0.,cf/m,0.,lf*cf/iz]);e=np.array([0.,0.,-v,0.])
    augmented=np.zeros((6,6));augmented[:4,:4]=a;augmented[:4,4]=b;augmented[:4,5]=e
    discrete=expm(augmented*dt);ad=discrete[:4,:4];bd=discrete[:4,4];ed=discrete[:4,5]
    sx=np.zeros((4*n,4));su=np.zeros((4*n,n));sk=np.zeros((4*n,n))
    for i in range(n):
        sx[4*i:4*i+4]=np.linalg.matrix_power(ad,i+1)
        for j in range(i+1):
            power=np.linalg.matrix_power(ad,i-j);su[4*i:4*i+4,j]=power@bd;sk[4*i:4*i+4,j]=power@ed
    q=np.diag([8.,0.,2.,0.]);qbar=block_diag(*([q*dt]*n));difference=np.eye(n)
    difference[np.arange(1,n),np.arange(n-1)]=-1.
    aa=np.zeros((5,5));aa[:4,:4]=ad;bb=np.r_[bd,1.][:,None]
    qq=np.zeros((5,5));qq[:4,:4]=q*dt;qq[4,4]=.02/dt
    cross=np.zeros((5,1));cross[4,0]=-.02/dt
    terminal=solve_discrete_are(aa,bb,qq,np.array([[.03*dt+.02/dt]]),s=cross)
    mapping=np.vstack([su[-4:],np.eye(n)[-1:]])
    hessian=2*(su.T@qbar@su+.03*dt*np.eye(n)+.02/dt*difference.T@difference+mapping.T@terminal@mapping)
    before_sx=np.vstack([np.eye(4),sx[:-4]]);before_su=np.vstack([np.zeros((4,n)),su[:-4]])
    before_sk=np.vstack([np.zeros((4,n)),sk[:-4]])
    k=gain(speed,penalty,stiffness);kp=np.array([k[0],k[1],k[1]*v+k[2],k[3]])
    transformed=block_diag(*([kp[None,:]]*n))
    residual_matrix=np.eye(n)+transformed@before_su
    constraints=sparse.csc_matrix(np.vstack([np.eye(n),difference,residual_matrix,su[0::4]]))
    return sx,su,sk,qbar,difference,terminal,mapping,transformed,before_sx,before_sk,sparse.csc_matrix(np.triu(hessian)),constraints,k


class Planner:
    def __init__(self):self.solvers={};self.calls=0;self.failures=0;self.status='NOT_RUN'
    def plan(self,state,route,previous,cfg,stiffness,penalty):
        if state[3]<2.:return None
        self.calls+=1;v=max(2.,round(float(state[3])*2)/2);s=float(np.clip(round(stiffness*20)/20,.7,1.3));n=round(cfg.horizon/cfg.dt)
        key=(v,s,float(penalty),cfg.dt,n)
        sx,su,sk,qbar,difference,terminal,mapping,transform,before_sx,before_sk,p,am,k=matrices(*key)
        ref,h,_=route.geometry(state[0]);ep=np.arctan2(np.sin(state[2]-h),np.cos(state[2]-h))
        z=np.array([state[1]-ref,state[4],ep,state[5]])
        kappas=np.array([route.geometry(state[0]+v*i*cfg.dt)[2] for i in range(n)])
        length=2.6;cf=cr=80000*s
        ff=(length+1650/length*(1.4/cf-1.2/cr)*v*v)*kappas
        vy=(1.4*v-1650*1.2*v**3/(length*cr))*kappas
        target=np.column_stack([np.zeros(n),vy,-vy/v,v*kappas]).reshape(-1)
        free=sx@z+sk@kappas;offset=np.r_[previous,np.zeros(n-1)]
        terminal_free=np.r_[free[-4:]-target[-4:],-ff[-1]]
        gradient=2*(su.T@qbar@(free-target)-.02/cfg.dt*difference.T@offset+mapping.T@terminal@terminal_free)
        baseline_offset=ff-k[2]*vy/v+k[3]*v*kappas-transform@(before_sx@z+before_sk@kappas)
        rate=cfg.steering_rate*cfg.dt
        lower=np.r_[np.full(n,-cfg.steering_limit),offset-rate,baseline_offset-cfg.residual_limit,-1.75-free[0::4]]
        upper=np.r_[np.full(n,cfg.steering_limit),offset+rate,baseline_offset+cfg.residual_limit,1.75-free[0::4]]
        if key not in self.solvers:
            solver=osqp.OSQP();solver.setup(P=p,q=gradient,A=am,l=lower,u=upper,verbose=False,
                eps_abs=1e-6,eps_rel=1e-6,max_iter=3000,warm_start=True,polish=False)
            self.solvers[key]=solver
        else:self.solvers[key].update(q=gradient,l=lower,u=upper)
        solved=self.solvers[key].solve();self.status=solved.info.status
        if solved.info.status_val not in (1,2) or solved.x is None or not np.isfinite(solved.x).all():
            self.failures+=1;return None
        constrained=am@solved.x
        if max(float(np.max(lower-constrained)),float(np.max(constrained-upper)))>1e-4:
            self.failures+=1;self.status='constraint_violation';return None
        return solved.x.copy()
