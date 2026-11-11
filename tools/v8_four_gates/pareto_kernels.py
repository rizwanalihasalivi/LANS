"""Fast tracking-SSE rollout with unchanged physical/heading/rate measurements."""
import math
import numpy as np
from numba import njit
from tools.unified_control_v4.kernels import lqr,geometry
from .fast_kernels import step_inplace


@njit(cache=True)
def rollout(z,first,accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty_rate,steering_limit,steering_rate,feedback_stiffness=1.,plan=None):
    z=z.copy();cost=0.;margin=1e9;heading_energy=0.;rate_energy=0.
    for i in range(int(math.ceil(horizon/dt))):
        base=lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback_stiffness);steer=first if i==0 else base
        if i>0 and plan is not None and i<len(plan):steer=min(base+.08,max(base-.08,plan[i]))
        if i>0:steer=min(previous+steering_rate*dt,max(previous-steering_rate*dt,steer))
        steer=min(steering_limit,max(-steering_limit,steer));step_inplace(z,steer,accel,dt,stiff)
        y,h,_=geometry(z[0],int(route[0]),route[1],route[2],route[3]);ey=z[1]-y;ep=math.atan2(math.sin(z[2]-h),math.cos(z[2]-h));rate=(steer-previous)/dt
        cost+=dt*ey*ey;heading_energy+=dt*ep*ep;rate_energy+=dt*rate*rate;margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for n in npcs:
            vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*t-z[0];dy=n[1]+vy*t-z[1];margin=min(margin,math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty_rate*t)
        previous=steer
    return cost,margin,heading_energy,rate_energy
