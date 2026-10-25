"""Privileged paired counterfactual reward, never an actor observation."""
import math
import numpy as np
from numba import njit
from bootstrap import RESEARCH
from core import reference
from plant import advance

@njit(cache=True)
def path_at(x,path):
    y,d,dd=reference(x,*path)
    return y,math.atan(d),dd/(1+d*d)**1.5

@njit(cache=True)
def true_feedback(s,v,path,gain):
    y,heading,kappa=path_at(s[0],path)
    vyref=(1.4*v-1650*1.2*v**3/(2.6*80000))*kappa
    error=np.array([s[1]-y,s[3]-vyref,s[2]-heading+vyref/v,s[4]-v*kappa])
    ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*v*v)*kappa
    return max(-.5,min(.5,ff-np.dot(gain,error)))

@njit(cache=True)
def tracking_cost(s,path):
    y,heading,_=path_at(s[0],path)
    return ((s[1]-y)/.5)**2+.2*((s[2]-heading)/.1)**2

@njit(cache=True)
def rollout_cost(state,first_command,v,path,mu,stiffness,gain):
    s=state.copy();cost=0.
    for i in range(10):
        u=first_command if i==0 else true_feedback(s,v,path,gain)
        s=advance(s,u,v,mu,stiffness)
        cost+=.01*tracking_cost(s,path)
    return cost+.1*tracking_cost(s,path)

def relative_bonus(state,command,baseline,v,path,mu,stiffness,gain):
    j0=rollout_cost(state,baseline,v,path,mu,stiffness,gain)
    j1=j0 if command==baseline else rollout_cost(state,command,v,path,mu,stiffness,gain)
    return float(np.clip((j0-j1)/(1e-4+j0),-1.,1.)),float(j0),float(j1)
