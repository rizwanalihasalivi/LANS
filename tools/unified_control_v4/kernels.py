"""Compiled nominal-model rollout, independently checked against Python physics."""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def geometry(x,kind,mirror,phase,amplitude):
    x+=phase
    if kind==0:return 0.,0.,0.
    if kind==1:
        w=2*math.pi/120;y=1.5*math.sin(w*x);d=1.5*w*math.cos(w*x);dd=-1.5*w*w*math.sin(w*x)
    else:
        t=math.tanh((x-30)/12);y=1.75*(1+t);d=1.75*(1-t*t)/12;dd=-3.5*t*(1-t*t)/144
    scale=mirror*amplitude;d*=scale;dd*=scale
    return scale*y,math.atan(d),dd/(1+d*d)**1.5


@njit(cache=True)
def lqr(z,gains,kind,mirror,phase,amplitude,nominal_stiffness=1.):
    y,h,k=geometry(z[0],kind,mirror,phase,amplitude)
    ep=math.atan2(math.sin(z[2]-h),math.cos(z[2]-h));v=max(2.,z[3])
    index=int(round(v*2));index=min(len(gains)-1,max(4,index))
    vyref=(1.4*v-1650*1.2*v**3/(2.6*80000*nominal_stiffness))*k
    e=np.array([z[1]-y,z[4]+z[3]*ep,ep+vyref/v,z[5]-z[3]*k])
    ff=(2.6+1650/2.6*(1.4/(80000*nominal_stiffness)-1.2/(80000*nominal_stiffness))*v*v)*k
    return min(.5,max(-.5,ff-np.dot(gains[index],e)))


@njit(cache=True)
def derivative(z,steer,accel,stiff):
    h,v,vy,r=z[2],max(0.,z[3]),z[4],z[5]
    if v<2.:dy=-10*vy;dr=10*(v*math.tan(steer)/2.6-r)
    else:
        f=80000*stiff*(steer-(vy+1.2*r)/v);b=80000*stiff*(-(vy-1.4*r)/v)
        dy=(f+b)/1650-v*r;dr=(1.2*f-1.4*b)/4224
    a=accel if v>0 or accel>0 else 0.
    return np.array([v*math.cos(h)-vy*math.sin(h),v*math.sin(h)+vy*math.cos(h),r,a,dy,dr])


@njit(cache=True)
def step(z,steer,accel,dt,stiff):
    state=z.copy();n=max(1,int(math.ceil(dt/.01)));h=dt/n
    for _ in range(n):
        a=derivative(state,steer,accel,stiff);b=derivative(state+h*a/2,steer,accel,stiff)
        c=derivative(state+h*b/2,steer,accel,stiff);d=derivative(state+h*c,steer,accel,stiff)
        state+=h*(a+2*b+2*c+d)/6;state[3]=max(0.,state[3])
    return state


@njit(cache=True)
def rollout(z,first,accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty_rate,steering_limit,steering_rate,feedback_stiffness=1.,plan=None):
    z=z.copy();cost=0.;margin=1e9;heading_energy=0.;rate_energy=0.
    for i in range(int(math.ceil(horizon/dt))):
        base=lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback_stiffness)
        steer=first if i==0 else base
        if i>0 and plan is not None and i<len(plan):steer=min(base+.08,max(base-.08,plan[i]))
        if i>0:steer=min(previous+steering_rate*dt,max(previous-steering_rate*dt,steer))
        steer=min(steering_limit,max(-steering_limit,steer));z=step(z,steer,accel,dt,stiff)
        y,h,_=geometry(z[0],int(route[0]),route[1],route[2],route[3])
        ey=z[1]-y;ep=math.atan2(math.sin(z[2]-h),math.cos(z[2]-h));rate=(steer-previous)/dt
        heading_energy+=dt*ep*ep;rate_energy+=dt*rate*rate
        cost+=dt*(8*ey*ey+2*ep*ep+.03*steer*steer+.02*rate*rate)
        margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for j in range(len(npcs)):
            n=npcs[j];vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*t-z[0];dy=n[1]+vy*t-z[1]
            clearance=math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty_rate*t
            margin=min(margin,clearance)
        previous=steer
    return cost,margin,heading_energy,rate_energy
