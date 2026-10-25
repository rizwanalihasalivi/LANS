"""Isolated mismatch plant. Its hidden parameters are never passed to the gate."""
import math
import numpy as np
from numba import njit
from core import fiala

@njit(cache=True)
def derivative(s,u,v,mu,stiffness):
    x,y,psi,vy,r,delta=s
    front=fiala(delta-math.atan2(vy+1.2*r,v),80000*stiffness,1650*9.81*1.4/2.6,mu)
    rear=fiala(-math.atan2(vy-1.4*r,v),80000*stiffness,1650*9.81*1.2/2.6,mu)
    return np.array([v*math.cos(psi)-vy*math.sin(psi),v*math.sin(psi)+vy*math.cos(psi),r,
                     (front*math.cos(delta)+rear)/1650-v*r,(1.2*front*math.cos(delta)-1.4*rear)/4224,
                     max(-.35,min(.35,(max(-.5,min(.5,u))-delta)/.05))])

@njit(cache=True)
def advance(s,u,v,mu,stiffness):
    value=s.copy();dt=.001
    for _ in range(10):
        a=derivative(value,u,v,mu,stiffness);b=derivative(value+.5*dt*a,u,v,mu,stiffness)
        c=derivative(value+.5*dt*b,u,v,mu,stiffness);d=derivative(value+dt*c,u,v,mu,stiffness)
        value+=dt/6*(a+2*b+2*c+d);value[5]=max(-.5,min(.5,value[5]))
    return value
