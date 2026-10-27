"""Allocation-free scalar replica of the frozen v3 nominal predictor."""
import boot4
import math
from numba import njit


@njit(cache=True)
def scalar_cost(z0,actuator,speed,ks,gain,filtered,residual,weight):
    ey,vy,ep,r=z0[0],z0[1],z0[2],z0[3]
    delta=actuator;f=filtered;cost=0.;alpha=1-math.exp(-.01/.3)
    g0,g1,g2,g3=gain[0],gain[1],gain[2],gain[3]
    for i in range(100):
        d=speed*i*.01
        k=ks[0]+(ks[1]-ks[0])*d/10 if d<10 else (ks[1]+(ks[2]-ks[1])*(d-10)/10 if d<20 else ks[2])
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*k
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed*speed)*k
        feedback=g0*ey+g1*(vy-vyref)+g2*(ep+vyref/speed)+g3*(r-speed*k)
        base=max(-.5,min(.5,ff-feedback))
        if i:f+=alpha*(residual-f)
        u=max(-.5,min(.5,base+weight*f));rate=max(-.35,min(.35,(u-delta)/.05));delta+=.01*rate
        front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        ney=ey+.01*(vy+speed*ep);nvy=vy+.01*((front+rear)/1650-speed*r)
        nep=ep+.01*(r-speed*k);nr=r+.01*(1.2*front-1.4*rear)/4224
        ey,vy,ep,r=ney,nvy,nep,nr
        cost+=.01*((ey/.5)**2+.2*(ep/.1)**2+.2*(rate/.35)**2+.005*(u/.5)**2)
    return cost
