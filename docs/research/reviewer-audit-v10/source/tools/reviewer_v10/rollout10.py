"""Nominal-model RK4 integration and executed average-actuator-rate cost.
No true plant friction/stiffness, future noise or future policy outputs are used.
"""
import boot10
import math
from numba import njit

@njit(cache=True)
def curvature_at(t,speed,ks):
    d=speed*t
    return ks[0]+(ks[1]-ks[0])*d/10 if d<10 else (ks[1]+(ks[2]-ks[1])*(d-10)/10 if d<20 else ks[2])

@njit(cache=True)
def derivative(z,u,speed,k):
    ey,vy,ep,r,delta=z
    front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
    return (vy+speed*ep,(front+rear)/1650-speed*r,r-speed*k,(1.2*front-1.4*rear)/4224,max(-.35,min(.35,(u-delta)/.05)))

@njit(cache=True)
def micro_step(z,u,speed,ks,t,dt):
    a=derivative(z,u,speed,curvature_at(t,speed,ks))
    b=derivative((z[0]+dt*.5*a[0],z[1]+dt*.5*a[1],z[2]+dt*.5*a[2],z[3]+dt*.5*a[3],z[4]+dt*.5*a[4]),u,speed,curvature_at(t+dt*.5,speed,ks))
    c=derivative((z[0]+dt*.5*b[0],z[1]+dt*.5*b[1],z[2]+dt*.5*b[2],z[3]+dt*.5*b[3],z[4]+dt*.5*b[4]),u,speed,curvature_at(t+dt*.5,speed,ks))
    d=derivative((z[0]+dt*c[0],z[1]+dt*c[1],z[2]+dt*c[2],z[3]+dt*c[3],z[4]+dt*c[4]),u,speed,curvature_at(t+dt,speed,ks))
    return (z[0]+dt/6*(a[0]+2*b[0]+2*c[0]+d[0]),z[1]+dt/6*(a[1]+2*b[1]+2*c[1]+d[1]),z[2]+dt/6*(a[2]+2*b[2]+2*c[2]+d[2]),z[3]+dt/6*(a[3]+2*b[3]+2*c[3]+d[3]),z[4]+dt/6*(a[4]+2*b[4]+2*c[4]+d[4]))

@njit(cache=True)
def rk_cost(z0,actuator,speed,ks,gain,filtered,residual,weight,assisted_steps):
    z=(z0[0],z0[1],z0[2],z0[3],actuator);f=filtered;cost=0.;alpha=1-math.exp(-.01/.3)
    for i in range(100):
        k=curvature_at(i*.01,speed,ks)
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*k
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed*speed)*k
        feedback=gain[0]*z[0]+gain[1]*(z[1]-vyref)+gain[2]*(z[2]+vyref/speed)+gain[3]*(z[3]-speed*k)
        base=max(-.5,min(.5,ff-feedback))
        if i and i<assisted_steps:f+=alpha*(residual-f)
        u=max(-.5,min(.5,base+(weight*f if i<assisted_steps else 0.)));old=z[4]
        for j in range(10):z=micro_step(z,u,speed,ks,i*.01+j*.001,.001)
        rate=(z[4]-old)/.01
        cost+=.01*((z[0]/.5)**2+.2*(z[2]/.1)**2+.2*(rate/.35)**2+.005*(u/.5)**2)
    return cost
