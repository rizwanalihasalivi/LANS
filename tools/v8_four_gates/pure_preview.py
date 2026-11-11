"""Preview LQT for measured lateral/body-heading/increment objectives.

Steady-road continuation is included in the terminal affine value. Heading is
absolute body error, matching scoring, rather than its equilibrium deviation.
"""
from functools import lru_cache
import math
import numpy as np
from scipy.linalg import expm,solve_discrete_are


@lru_cache(maxsize=8192)
def gains(speed,stiffness,heading_weight,increment_weight,yaw_weight,horizon=40):
    v=max(2.,float(speed));cf=cr=80000.*stiffness;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0.,1.,v,0.],[0.,-(cf+cr)/(m*v),0.,(cr*lr-cf*lf)/(m*v)-v],
        [0.,0.,0.,1.],[0.,(cr*lr-cf*lf)/(iz*v),0.,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
    block=np.zeros((6,6));block[:4,:4]=a;block[:4,4]=[0.,cf/m,0.,cf*lf/iz];block[:4,5]=[0.,0.,-v,0.]
    discrete=expm(block*.05);aa=np.zeros((5,5));aa[:4,:4]=discrete[:4,:4];aa[:4,4]=discrete[:4,4];aa[4,4]=1.
    bb=np.r_[discrete[:4,4],1.][:,None];dd=np.r_[discrete[:4,5],0.]
    q=np.diag([1.,0.,heading_weight,yaw_weight,1e-8]);r=np.array([[increment_weight]])
    p=solve_discrete_are(aa,bb,q,r);hh=float((r+bb.T@p@bb)[0,0]);k=(bb.T@p@aa/hh).ravel();closed=aa-bb@k[None,:]
    gradient=np.array([0.,0.,0.,-yaw_weight*v,0.]);s_constant=np.linalg.solve(np.eye(5)-closed.T,closed.T@p@dd+gradient)
    term=p@dd;linear=gradient.copy();preview=[]
    for j in range(horizon):
        value=float((-bb.T@term/hh)[0])
        if j:value+=float((-bb.T@linear/hh)[0]);linear=closed.T@linear
        preview.append(value);term=closed.T@term
    terminal=s_constant.copy()
    for _ in range(horizon-1):terminal=closed.T@terminal
    preview[-1]+=float((-bb.T@terminal/hh)[0])
    return k,np.asarray(preview)


def command(state,previous,route,heading_weight=4.,increment_weight=64.,yaw_weight=0.,stiffness=1.):
    v=max(2.,round(float(state[3])*2)/2);stiffness=round(float(stiffness)*20)/20
    k,preview=gains(v,stiffness,heading_weight,increment_weight,yaw_weight)
    y,h,_=route.geometry(state[0]);ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h))
    z=np.array([state[1]-y,state[4],ep,state[5],previous]);curv=np.array([route.geometry(state[0]+max(0.,state[3])*i*.05)[2] for i in range(len(preview))])
    return float(previous-k@z+preview@curv)
