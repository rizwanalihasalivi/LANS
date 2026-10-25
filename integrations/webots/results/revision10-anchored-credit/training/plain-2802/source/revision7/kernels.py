"""Compiled replicas of frozen sensing/gate contracts for bounded branch rollouts.

Checked against original Sensor, Gate, Execution and RK4 transition behavior.
No learned model or hidden parameter is provided to the gate kernel.
"""
import math
import numpy as np
from numba import njit
from bootstrap import RESEARCH
from core import reference
from plant import advance
from gating import predict_cost


@njit(cache=True)
def path_values(x,path):
    y,d,dd=reference(x,*path)
    return y,math.atan(d),dd/(1+d*d)**1.5


@njit(cache=True)
def gain_at(speed,gains):
    return np.array([np.interp(speed,np.array([15.,20.,25.]),gains[:,i]) for i in range(4)])


@njit(cache=True)
def lqr(estimate,speed,curvature,gains):
    gain=gain_at(speed,gains)
    vy=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    target=np.array([0.,vy,-vy/speed,speed*curvature])
    ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
    return max(-.5,min(.5,ff-np.dot(gain,estimate-target))),gain


@njit(cache=True)
def measure(state,speed,path,noise,delay,estimate,cov,previous_raw,first,noise_scale):
    y,heading,curvature=path_values(state[0],path)
    raw=np.array([state[1]-y,state[2]-heading,state[4],speed])+noise
    z=previous_raw.copy() if delay and not first else raw.copy()
    v=max(5.,z[3]);cf=cr=80000.;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0.,1.,v,0.],[0.,-(cf+cr)/(m*v),0.,(cr*lr-cf*lf)/(m*v)-v],
                [0.,0.,0.,1.],[0.,(cr*lr-cf*lf)/(iz*v),0.,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
    ad=np.eye(4)+.01*a;b=.01*np.array([0.,cf/m,0.,cf*lf/iz])
    prediction=np.array([z[0],0.,z[1],z[2]]) if first else ad@estimate+b*state[5]+np.array([0.,0.,-v*curvature*.01,0.])
    updated_cov=ad@cov@ad.T+np.diag(np.array([1e-7,1e-4,1e-8,1e-5]))
    h=np.array([[1.,0.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])
    variances=np.array([.03,math.radians(.17),.01])**2*max(noise_scale,.01)**2
    innovation=h@updated_cov@h.T+np.diag(variances)
    kalman=np.linalg.solve(innovation,(updated_cov@h.T).T).T
    prediction+=kalman@(z[:3]-h@prediction)
    updated_cov=(np.eye(4)-kalman@h)@updated_cov
    # Actor/gate use original float32 speed channel, then promote it back to float64.
    measured=max(5.,np.float64(np.float32(v/25))*25)
    return prediction,updated_cov,raw,measured,curvature


@njit(cache=True)
def reset_gate(executor,baseline,reason,j0=np.nan,j1=np.nan):
    executor[0]=0.;executor[1]=0.
    return baseline,0.,reason,j0,j1


@njit(cache=True)
def gate(executor,t,baseline,estimate,actuator,speed,curvature,gain):
    # state0:weight,1:good,2:last_gate_seq,3:packet_seq,4:observed,5:residual
    if executor[3]<0:return reset_gate(executor,baseline,0)
    if not np.isfinite(np.array([t,baseline,executor[4],executor[5],actuator,speed,curvature])).all() or not np.isfinite(estimate).all():
        return reset_gate(executor,baseline,7)
    age=t-executor[4]
    if age<0 or age>=.05:return reset_gate(executor,baseline,1)
    if executor[3]<executor[2]:return reset_gate(executor,baseline,2)
    executor[2]=executor[3]
    if abs(estimate[0])>1.5 or abs(estimate[2])>.25:return reset_gate(executor,baseline,3)
    candidate=max(-.5,min(.5,baseline+max(-.08,min(.08,executor[5]))))
    fresh=max(0.,min(1.,(.05-age)/.04))
    j0=predict_cost(estimate,actuator,baseline,speed,curvature,gain,20)
    best=j0;weight=0.;command=baseline
    for limit in (.1,.25,.5):
        w=min(limit*fresh,executor[0]+.05);u=(1-w)*baseline+w*candidate
        value=predict_cost(estimate,actuator,u,speed,curvature,gain,20)
        if value<best:best=value;weight=w;command=u
    if not math.isfinite(j0) or not math.isfinite(best):return reset_gate(executor,baseline,8,j0,best)
    if weight==0 or j0-best<max(1e-7,.01*j0):return reset_gate(executor,baseline,4,j0,best)
    executor[1]+=1
    if executor[1]<3:
        executor[0]=0.
        return baseline,0.,5,j0,best
    executor[0]=weight
    return command,weight,6,j0,best


@njit(cache=True)
def execution_step(executor,t,proposal,service,baseline,estimate,actuator,speed,curvature,gain,bypass):
    # 6:pending_ready,7:pending_seq,8:pending_observed,9:pending_residual,
    # 10:sequence,11:last_command. Missing packet/pending has sequence -1.
    if executor[7]>=0 and executor[6]<=t+1e-9:
        executor[3]=executor[7];executor[4]=executor[8];executor[5]=executor[9];executor[7]=-1.
    submitted=executor[7]<0
    if submitted:
        executor[10]+=1
        if service==0:
            executor[3]=executor[10];executor[4]=t;executor[5]=max(-.08,min(.08,proposal))
        else:
            executor[6]=t+service*.01;executor[7]=executor[10];executor[8]=t;executor[9]=max(-.08,min(.08,proposal))
    if bypass:
        age=t-executor[4]
        if executor[3]<0:command,weight,reason=baseline,0.,0
        elif age<0 or age>=.05:command,weight,reason=baseline,0.,1
        else:command,weight,reason=max(-.5,min(.5,baseline+executor[5])),1.,9
        executor[0]=weight;executor[1]=3. if weight else 0.
    else:
        command,weight,reason,_,_=gate(executor,t,baseline,estimate,actuator,speed,curvature,gain)
    executor[11]=command
    return command,weight,reason,submitted


@njit(cache=True)
def branch_cost(state,estimate,cov,previous_raw,executor,tick,proposal,service,speed,path,mu,stiffness,
                noises,delay,noise_scale,measured,curvature,gains,bypass,horizon):
    z=state.copy();est=estimate.copy();variance=cov.copy();previous=previous_raw.copy();worker=executor.copy()
    cost=0.;v=measured;kappa=curvature
    for j in range(horizon):
        baseline,gain=lqr(est,v,kappa,gains)
        command,_,_,_=execution_step(worker,(tick+j)*.01,proposal,service,baseline,est,z[5],v,kappa,gain,bypass)
        z=advance(z,command,speed,mu,stiffness)
        y,heading,_=path_values(z[0],path);ey=z[1]-y
        cost+=ey*ey
        if abs(ey)>2.5 or abs(z[2]-heading)>.6 or not np.isfinite(z).all():
            return cost+(horizon-j-1)*6.25
        if j+1<horizon:
            est,variance,previous,v,kappa=measure(z,speed,path,noises[tick+j+1],delay,est,variance,previous,False,noise_scale)
    return cost


@njit(cache=True)
def select(state,estimate,cov,previous_raw,executor,tick,service,speed,path,mu,stiffness,noises,delay,
           noise_scale,measured,curvature,gains,bypass,horizon,candidates):
    costs=np.empty(len(candidates));index=0
    for i in range(len(candidates)):
        costs[i]=branch_cost(state,estimate,cov,previous_raw,executor,tick,candidates[i],service,speed,path,mu,
            stiffness,noises,delay,noise_scale,measured,curvature,gains,bypass,horizon)
        if costs[i]<costs[index] or (costs[i]==costs[index] and abs(candidates[i])<abs(candidates[index])):index=i
    return candidates[index],index,costs


def initial_executor():
    values=np.zeros(12,dtype=np.float64)
    values[2]=-1.;values[3]=-1.;values[7]=-1.
    return values


@njit(cache=True)
def simulate(method,speed,path,mu,stiffness,noise_scale,delay,service,noises,gains,candidates,horizon,scheduled):
    y,heading,_=path_values(0.,path)
    state=np.array([0.,y+.15,heading+.01,0.,0.,0.])
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4)
    executor=np.zeros(12);executor[2]=-1.;executor[3]=-1.;executor[7]=-1.
    # tick,time,x,y,heading,reference,error,command,actuator,baseline,weight,
    # reason,proposal,selected,cost0..4,packet_seq,observed,pending_seq,good
    trace=np.full((scheduled,23),np.nan);failed=False;calls=0
    for tick in range(scheduled):
        estimate,cov,previous,measured,curvature=measure(state,speed,path,noises[tick],delay,estimate,cov,previous,tick==0,noise_scale)
        baseline,gain=lqr(estimate,measured,curvature,gains)
        proposal=0.;index=-1;costs=np.full(5,np.nan)
        if method==0:command=baseline;weight=0.;reason=10
        else:
            available=executor[7]<0 or executor[6]<=tick*.01+1e-9
            if method in (6,7) and available:
                proposal,index,costs=select(state,estimate,cov,previous,executor,tick,service,speed,path,mu,stiffness,
                    noises,delay,noise_scale,measured,curvature,gains,method==7,horizon,candidates)
                calls+=1
            elif 1<=method<=5:proposal=candidates[method-1]
            command,weight,reason,_=execution_step(executor,tick*.01,proposal,service,baseline,estimate,state[5],measured,curvature,gain,method==7)
        state=advance(state,command,speed,mu,stiffness)
        reference,heading,_=path_values(state[0],path);error=state[1]-reference
        trace[tick,:14]=np.array([tick,(tick+1)*.01,state[0],state[1],state[2],reference,error,command,state[5],baseline,weight,reason,proposal,index])
        trace[tick,14:19]=costs
        trace[tick,19:23]=np.array([executor[3],executor[4],executor[7],executor[1]])
        if abs(error)>2.5 or abs(state[2]-heading)>.6 or not np.isfinite(state).all():
            failed=True
            return trace[:tick+1],failed,calls
    return trace,failed,calls
