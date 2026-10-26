"""Small fixed-size observer algebra without BLAS/LAPACK dispatch.

Same observer equations as revision7. This is an implementation optimization,
not changed noise, gain, timing, policy or gate semantics.
"""
import sys
from pathlib import Path
import math
import numpy as np
from numba import njit
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'integrations/webots/research/revision8'))
import bootstrap
from kernels import path_values


@njit(cache=True)
def small_product(a,b):
    out=np.zeros((a.shape[0],b.shape[1]))
    for i in range(a.shape[0]):
        for j in range(b.shape[1]):
            for k in range(a.shape[1]):out[i,j]+=a[i,k]*b[k,j]
    return out


@njit(cache=True)
def small_vector(a,b):
    out=np.zeros(a.shape[0])
    for i in range(a.shape[0]):
        for j in range(a.shape[1]):out[i]+=a[i,j]*b[j]
    return out


@njit(cache=True)
def solve_spd3(a,b):
    # The innovation covariance is positive definite (nonzero measurement noise).
    lower=np.zeros((3,3))
    for i in range(3):
        for j in range(i+1):
            value=a[i,j]
            for k in range(j):value-=lower[i,k]*lower[j,k]
            if i==j:
                if not math.isfinite(value) or value<=0:raise ValueError('invalid innovation covariance')
                lower[i,j]=math.sqrt(value)
            else:lower[i,j]=value/lower[j,j]
    y=np.zeros_like(b);x=np.zeros_like(b)
    for col in range(b.shape[1]):
        for i in range(3):
            value=b[i,col]
            for j in range(i):value-=lower[i,j]*y[j,col]
            y[i,col]=value/lower[i,i]
        for i in range(2,-1,-1):
            value=y[i,col]
            for j in range(i+1,3):value-=lower[j,i]*x[j,col]
            x[i,col]=value/lower[i,i]
    return x


@njit(cache=True)
def measure_fast(state,speed,path,noise,delay,estimate,cov,previous_raw,first,noise_scale):
    y,heading,curvature=path_values(state[0],path)
    raw=np.array([state[1]-y,state[2]-heading,state[4],speed])+noise
    z=previous_raw.copy() if delay and not first else raw.copy()
    v=max(5.,z[3]);cf=cr=80000.;m=1650.;iz=4224.;lf=1.2;lr=1.4
    a=np.array([[0.,1.,v,0.],[0.,-(cf+cr)/(m*v),0.,(cr*lr-cf*lf)/(m*v)-v],
                [0.,0.,0.,1.],[0.,(cr*lr-cf*lf)/(iz*v),0.,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
    ad=np.eye(4)+.01*a;b=.01*np.array([0.,cf/m,0.,cf*lf/iz])
    prediction=np.array([z[0],0.,z[1],z[2]]) if first else small_vector(ad,estimate)+b*state[5]+np.array([0.,0.,-v*curvature*.01,0.])
    updated_cov=small_product(small_product(ad,cov),ad.T)+np.diag(np.array([1e-7,1e-4,1e-8,1e-5]))
    h=np.array([[1.,0.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])
    variances=np.array([.03,math.radians(.17),.01])**2*max(noise_scale,.01)**2
    innovation=small_product(small_product(h,updated_cov),h.T)+np.diag(variances)
    kalman=solve_spd3(innovation,small_product(updated_cov,h.T).T).T
    prediction+=small_vector(kalman,(z[:3]-small_vector(h,prediction)))
    updated_cov=small_product((np.eye(4)-small_product(kalman,h)),updated_cov)
    # Actor/gate use original float32 speed channel, then promote it back to float64.
    measured=max(5.,np.float64(np.float32(v/25))*25)
    return prediction,updated_cov,raw,measured,curvature

