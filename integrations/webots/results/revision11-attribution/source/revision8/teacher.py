"""Teacher never receives the actual future measurement-noise buffer."""
import math
import numpy as np
from numba import njit
from bootstrap import RESEARCH
from kernels import measure,lqr,execution_step,path_values
from plant import advance


@njit(cache=True)
def expected_cost(state,estimate,cov,previous_raw,executor,tick,proposal,service,speed,path,mu,stiffness,
                  forecast,delay,noise_scale,measured,curvature,gains):
    total=0.
    for sign in (0.,1.,-1.):
        z=state.copy();est=estimate.copy();variance=cov.copy();previous=previous_raw.copy();worker=executor.copy()
        v=measured;k=curvature;value=0.
        for j in range(20):
            baseline,gain=lqr(est,v,k,gains)
            command,_,_,_=execution_step(worker,(tick+j)*.01,proposal,service,baseline,est,z[5],v,k,gain,False)
            z=advance(z,command,speed,mu,stiffness)
            y,h,_=path_values(z[0],path);ey=z[1]-y;value+=ey*ey
            if abs(ey)>2.5 or abs(z[2]-h)>.6 or not np.isfinite(z).all():
                value+=(19-j)*6.25;break
            if j<19:
                est,variance,previous,v,k=measure(z,speed,path,sign*forecast[j+1],delay,est,variance,previous,False,noise_scale)
        total+=value
    return total/3.


@njit(cache=True)
def choose(state,estimate,cov,previous_raw,executor,tick,service,speed,path,mu,stiffness,forecast,
           delay,noise_scale,measured,curvature,gains):
    candidates=np.array([-.08,-.04,0.,.04,.08]);costs=np.empty(5);selected=0
    for i in range(5):
        costs[i]=expected_cost(state,estimate,cov,previous_raw,executor,tick,candidates[i],service,speed,path,mu,stiffness,
            forecast,delay,noise_scale,measured,curvature,gains)
        if costs[i]<costs[selected] or (costs[i]==costs[selected] and abs(candidates[i])<abs(candidates[selected])):selected=i
    if costs[2]-costs[selected]<=max(1e-7,.001*costs[2]):selected=2
    return selected,costs


@njit(cache=True)
def features(state,estimate,raw_speed,path,executor,tick,service):
    ey,vy,ep,r=estimate;t=tick*.01;packet=executor[3]>=0;pending=executor[7]>=0
    preview=np.array([path_values(state[0]+d,path)[2] for d in (0.,10.,20.)])
    return np.array([ey/3,ep/.3,(vy+raw_speed*ep)/5,r/.5,raw_speed/25,state[5]/.5,
        preview[0]/.02,preview[1]/.02,preview[2]/.02,
        executor[0],min(executor[1],3.)/3.,executor[5]/.08 if packet else 0.,
        (t-executor[4])/.1 if packet else 0.,1. if packet else 0.,
        executor[9]/.08 if pending else 0.,max(0.,executor[6]-t)/.1 if pending else 0.,
        (t-executor[8])/.1 if pending else 0.,1. if pending else 0.,executor[11]/.5,service/10.],dtype=np.float32)
