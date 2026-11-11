"""Cheap discrete-time LQ preview, with explicit steering-increment state."""
from functools import lru_cache
import math
import numpy as np
from scipy.linalg import expm,solve_discrete_are


@lru_cache(maxsize=4096)
def gains(speed,stiffness,heading_weight,increment_weight,horizon=40):
    v=max(2.,float(speed));cf=cr=80000.*stiffness;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0.,1.,v,0.],[0.,-(cf+cr)/(m*v),0.,(cr*lr-cf*lf)/(m*v)-v],
                [0.,0.,0.,1.],[0.,(cr*lr-cf*lf)/(iz*v),0.,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
    b=np.array([0.,cf/m,0.,cf*lf/iz]);d=np.array([0.,0.,-v,0.])
    block=np.zeros((6,6));block[:4,:4]=a;block[:4,4]=b;block[:4,5]=d
    discrete=expm(block*.05);aa=np.zeros((5,5));aa[:4,:4]=discrete[:4,:4];aa[:4,4]=discrete[:4,4];aa[4,4]=1.
    bb=np.r_[discrete[:4,4],1.][:,None];dd=np.r_[discrete[:4,5],0.]
    q=np.diag([1.,0.,heading_weight,0.,1e-4]);r=np.array([[increment_weight]])
    p=solve_discrete_are(aa,bb,q,r);h=float((r+bb.T@p@bb)[0,0]);k=(bb.T@p@aa/h).ravel();closed=aa-bb@k[None,:]
    term=p@dd;preview=[]
    for _ in range(horizon):preview.append(float((-bb.T@term/h)[0]));term=closed.T@term
    return k,np.asarray(preview)


def command(state,previous,route,heading_weight=1.,increment_weight=.2,stiffness=1.):
    v=max(2.,round(float(state[3])*2)/2);stiffness=round(float(stiffness)*20)/20
    k,preview=gains(v,stiffness,heading_weight,increment_weight)
    y,h,_=route.geometry(state[0]);ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h))
    z=np.array([state[1]-y,state[4],ep,state[5],previous])
    curv=np.array([route.geometry(state[0]+max(0.,state[3])*i*.05)[2] for i in range(len(preview))])
    return float(previous-k@z+preview@curv)
