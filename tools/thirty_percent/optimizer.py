"""Offline true-model shooting; requested residual and physical limits preserved."""
import math
import numpy as np
from numba import njit
from scipy.optimize import minimize
from tools.unified_control_v4.kernels import lqr,step,geometry


@njit(cache=True)
def rollout(actions,initial,accels,npcs,stiffness,gains,route):
    n=len(actions);states=np.zeros((n,6));steers=np.zeros(n);bases=np.zeros(n)
    state=initial.copy();previous=0.;sse=0.;heading=0.;slew=0.;corridor=1e9;clearance=1e9
    for i in range(n):
        base=lqr(state,gains,int(route[0]),route[1],route[2],route[3],1.)
        u=min(.5,max(-.5,min(previous+.03,max(previous-.03,base+.08*actions[i]))))
        state=step(state,u,accels[i],.05,stiffness)
        y,h,_=geometry(state[0],int(route[0]),route[1],route[2],route[3])
        ey=state[1]-y;ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h))
        sse+=ey*ey;heading+=ep*ep;slew+=((u-previous)/.05)**2
        corridor=min(corridor,1.75-abs(ey))
        for j in range(npcs.shape[1]):
            dx=state[0]-npcs[i,j,0];dy=state[1]-npcs[i,j,1]
            clearance=min(clearance,math.sqrt(dx*dx+dy*dy)-4.6)
        states[i]=state;steers[i]=u;bases[i]=base;previous=u
    return np.array([sse,heading,slew,state[0],corridor,clearance]),states,steers,bases


class Objective:
    def __init__(self,initial,accels,npcs,stiffness,gains,route,reference,quality):
        self.args=(initial,accels,npcs,stiffness,gains,route);self.reference=reference
        self.quality=quality;self.cache={};self.evaluations=0;self.jac_x=None;self.jac_value=None
    def values(self,x):
        key=x.tobytes()
        if key not in self.cache:
            if len(self.cache)>512:self.cache.clear()
            self.cache[key]=rollout(x,*self.args)[0];self.evaluations+=1
        return self.cache[key]
    def jacobian(self,x):
        if self.jac_x is None or not np.array_equal(x,self.jac_x):
            base=self.values(x);jac=np.empty((6,len(x)))
            for i in range(len(x)):
                trial=x.copy();delta=1e-5 if x[i]<=1.-1e-5 else -1e-5
                trial[i]+=delta;jac[:,i]=(self.values(trial)-base)/delta
            self.jac_x=x.copy();self.jac_value=jac
        return self.jac_value
    def fun(self,x):return self.values(x)[0]/self.reference[0]
    def grad(self,x):return self.jacobian(x)[0]/self.reference[0]
    def constraint(self,x):
        v=self.values(x);r=self.reference
        common=[v[3]/r[3]-.99000001,(v[4]-1e-8)/1.75,(v[5]-1e-6)/4.6]
        return np.array([1.21*(1-1e-6)-v[1]/r[1],1.21*(1-1e-6)-v[2]/r[2],*common] if self.quality else common)
    def constraint_jac(self,x):
        j=self.jacobian(x)
        r=self.reference;common=np.vstack([j[3]/r[3],j[4]/1.75,j[5]/4.6])
        return np.vstack([-j[1]/r[1],-j[2]/r[2],common]) if self.quality else common


def solve(initial,accels,npcs,stiffness,gains,route,reference,quality):
    objective=Objective(initial,accels,npcs,stiffness,gains,route,reference,quality)
    result=minimize(objective.fun,np.zeros(len(accels)),jac=objective.grad,method='SLSQP',
        bounds=[(-1.,1.)]*len(accels),constraints={'type':'ineq','fun':objective.constraint,'jac':objective.constraint_jac},
        options={'maxiter':120,'ftol':1e-10,'disp':False})
    return result,objective
