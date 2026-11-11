"""Allocation-free inner RK4 with the same equations/order as the frozen plant."""
import math
import numpy as np
from numba import njit
from tools.unified_control_v4.kernels import lqr,geometry


@njit(cache=True)
def derivative(x,y,h,v,vy,r,steer,accel,stiff):
    v=max(0.,v)
    if v<2.:dy=-10*vy;dr=10*(v*math.tan(steer)/2.6-r)
    else:
        f=80000*stiff*(steer-(vy+1.2*r)/v);b=80000*stiff*(-(vy-1.4*r)/v)
        dy=(f+b)/1650-v*r;dr=(1.2*f-1.4*b)/4224
    a=accel if v>0 or accel>0 else 0.
    return v*math.cos(h)-vy*math.sin(h),v*math.sin(h)+vy*math.cos(h),r,a,dy,dr


@njit(cache=True)
def step_inplace(z,steer,accel,dt,stiff):
    n=max(1,int(math.ceil(dt/.01)));h=dt/n
    x,y,psi,v,vy,r=z
    for _ in range(n):
        a=derivative(x,y,psi,v,vy,r,steer,accel,stiff)
        b=derivative(x+h*a[0]/2,y+h*a[1]/2,psi+h*a[2]/2,v+h*a[3]/2,vy+h*a[4]/2,r+h*a[5]/2,steer,accel,stiff)
        c=derivative(x+h*b[0]/2,y+h*b[1]/2,psi+h*b[2]/2,v+h*b[3]/2,vy+h*b[4]/2,r+h*b[5]/2,steer,accel,stiff)
        d=derivative(x+h*c[0],y+h*c[1],psi+h*c[2],v+h*c[3],vy+h*c[4],r+h*c[5],steer,accel,stiff)
        x+=h*(a[0]+2*b[0]+2*c[0]+d[0])/6;y+=h*(a[1]+2*b[1]+2*c[1]+d[1])/6
        psi+=h*(a[2]+2*b[2]+2*c[2]+d[2])/6;v=max(0.,v+h*(a[3]+2*b[3]+2*c[3]+d[3])/6)
        vy+=h*(a[4]+2*b[4]+2*c[4]+d[4])/6;r+=h*(a[5]+2*b[5]+2*c[5]+d[5])/6
    z[0]=x;z[1]=y;z[2]=psi;z[3]=v;z[4]=vy;z[5]=r


@njit(cache=True)
def step(z,steer,accel,dt,stiff):
    result=z.copy();step_inplace(result,steer,accel,dt,stiff);return result


@njit(cache=True)
def rollout(z,first,accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty_rate,steering_limit,steering_rate,feedback_stiffness=1.,plan=None):
    z=z.copy();cost=0.;margin=1e9;heading_energy=0.;rate_energy=0.
    for i in range(int(math.ceil(horizon/dt))):
        base=lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback_stiffness)
        steer=first if i==0 else base
        if i>0 and plan is not None and i<len(plan):steer=min(base+.08,max(base-.08,plan[i]))
        if i>0:steer=min(previous+steering_rate*dt,max(previous-steering_rate*dt,steer))
        steer=min(steering_limit,max(-steering_limit,steer));step_inplace(z,steer,accel,dt,stiff)
        y,h,_=geometry(z[0],int(route[0]),route[1],route[2],route[3]);ey=z[1]-y;ep=math.atan2(math.sin(z[2]-h),math.cos(z[2]-h));rate=(steer-previous)/dt
        heading_energy+=dt*ep*ep;rate_energy+=dt*rate*rate
        cost+=dt*(8*ey*ey+2*ep*ep+.03*steer*steer+.02*rate*rate)
        margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for j in range(len(npcs)):
            n=npcs[j];vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*t-z[0];dy=n[1]+vy*t-z[1]
            margin=min(margin,math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty_rate*t)
        previous=steer
    return cost,margin,heading_energy,rate_energy
