"""Eq5/Algorithm1 nominal linear specialization, not a nonlinear safety theorem."""
from collections import OrderedDict
from functools import lru_cache
import numpy as np
from scipy import sparse
from scipy.linalg import expm
import osqp


@lru_cache(maxsize=128)
def matrices(v,n):
    cf=cr=80000.;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0,1,v,0,0],[0,-(cf+cr)/(m*v),0,(cr*lr-cf*lf)/(m*v)-v,cf/m],
        [0,0,0,1,0],[0,(cr*lr-cf*lf)/(iz*v),0,-(cf*lf**2+cr*lr**2)/(iz*v),cf*lf/iz],
        [0,0,0,0,-20.]])
    b=np.array([0.,0.,0.,0.,20.]);e=np.array([0.,0.,-v,0.,0.])
    continuous=np.zeros((7,7));continuous[:5,:5]=a;continuous[:5,5]=b;continuous[:5,6]=e
    disc=expm(continuous*.01);ad,bd,ed=disc[:5,:5],disc[:5,5],disc[:5,6]
    powers=[np.eye(5)]
    for _ in range(n):powers.append(powers[-1]@ad)
    sx=np.zeros((5*n,5));su=np.zeros((5*n,n));sk=np.zeros((5*n,n))
    for i in range(n):
        sx[5*i:5*i+5]=powers[i+1]
        for j in range(i+1):
            su[5*i:5*i+5,j]=powers[i-j]@bd;sk[5*i:5*i+5,j]=powers[i-j]@ed
    previous=np.vstack([np.zeros((1,n)),su[4::5][:-1]])
    am=sparse.csc_matrix(np.vstack([np.eye(n),np.eye(n)-previous,
                                   su[0::5],su[2::5],su[4::5],su[-5:]]))
    diagonal=np.full(n,2e-8);diagonal[0]+=2
    return sx,su,sk,sparse.diags(diagonal,format='csc'),am


class NominalPSF:
    def __init__(self):
        self.solvers=OrderedDict();self.last_full=None;self.calls=0;self.fallbacks=0
        self.last_violation=0.;self.last_horizon=0;self.last_status='not_run'

    def solve(self,estimate,actuator,v,k,desired,n):
        sx,su,sk,hessian,am=matrices(v,n)
        x=np.r_[estimate,actuator];free=sx@x+sk@np.full(n,k)
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*v*v)*k
        vy=(1.4*v-1650*1.2*v**3/(2.6*80000))*k
        terminal=np.array([0.,vy,-vy/v,v*k,ff])
        before_delta=np.r_[actuator,free[4::5][:-1]]
        low=np.r_[np.full(n,-.5),before_delta-.0175,-1.5-free[0::5],-.25-free[2::5],-.5-free[4::5],terminal-free[-5:]]
        high=np.r_[np.full(n,.5),before_delta+.0175,1.5-free[0::5],.25-free[2::5],.5-free[4::5],terminal-free[-5:]]
        q=np.zeros(n);q[0]=-2*desired;key=(v,n)
        if key not in self.solvers:
            solver=osqp.OSQP();solver.setup(P=hessian,q=q,A=am,l=low,u=high,verbose=False,
                eps_abs=1e-6,eps_rel=1e-6,max_iter=3000,warm_start=True,polish=False)
            self.solvers[key]=solver
            if len(self.solvers)>64:self.solvers.popitem(last=False)
        else:
            solver=self.solvers[key];self.solvers.move_to_end(key);solver.update(q=q,l=low,u=high)
        result=solver.solve();self.last_status=result.info.status;self.last_horizon=n
        if result.info.status_val not in (1,2) or result.x is None or not np.isfinite(result.x).all():return None
        value=am@result.x
        violation=max(float(np.max(low-value)),float(np.max(value-high)),0.)
        self.last_violation=violation
        if violation>1e-4:return None
        return float(np.clip(result.x[0],-.5,.5))

    def command(self,estimate,actuator,speed,curvature,desired,baseline,tick):
        self.calls+=1;v=float(round(max(5.,speed),1))
        value=self.solve(estimate,actuator,v,curvature,desired,100)
        if value is not None:self.last_full=tick;return value,'full_feasible'
        if self.last_full is not None:
            remaining=100-(tick-self.last_full)
            if remaining>0:
                value=self.solve(estimate,actuator,v,curvature,desired,remaining)
                if value is not None:return value,'shortened_feasible'
        self.fallbacks+=1
        return baseline,'lqr_uncertified_fallback'
