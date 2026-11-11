"""Curvature-derivative feedforward from the bicycle's stable zero dynamics.

Reference lateral velocity/yaw are dynamically consistent, rather than a new
steady circle at every changing-curvature sample. Inputs are public state/map
and a causally identified model; no simulation-plant parameter is observed.
"""
from functools import lru_cache
import numpy as np
from integrations.unified_lans.physics import errors
from tools.unified_control_v4.control import gain,ScheduledLQR


@lru_cache(maxsize=4096)
def coefficients(speed,stiffness):
    v=max(2.,float(speed));cf=cr=80000.*stiffness;m=1650.;iz=4224.;lf=1.2;lr=1.4
    aa=(cf+cr)/(m*v);bb=(lf*cf-lr*cr)/(m*v);cc=cf/m
    dd=(lf*cf-lr*cr)/(iz*v);ee=(lf*lf*cf+lr*lr*cr)/(iz*v);ff=lf*cf/iz
    matrix=np.array([[0.,-v],[-dd+ff/cc*aa,-ee+ff/cc*bb]])
    forcing=np.array([v*v,ff/cc*v*v]);zero=-np.linalg.solve(matrix,forcing);first=np.linalg.solve(matrix,zero);second=np.linalg.solve(matrix,first)
    return zero,first,second,aa,bb,cc


def command(state,previous,route,order=1,weight=1.,adaptive_feedback=0,stiffness=1.):
    v=max(2.,float(state[3]));scheduled=max(2.,round(v*2)/2);s=round(float(stiffness)*20)/20
    zero,first,second,aa,bb,cc=coefficients(scheduled,s);e,kappa=errors(state,route)
    distance=max(.05,v*.05);left=route.geometry(state[0]-distance)[2];right=route.geometry(state[0]+distance)[2]
    derivative=v*(right-left)/(2*distance);second_derivative=v*v*(right-2*kappa+left)/(distance*distance)
    reference=zero*kappa
    if order>=1:reference=reference+first*derivative
    if order>=2:reference=reference+second*second_derivative
    vy,r=reference;feedforward=(aa*vy+bb*r+v*v*kappa)/cc
    target=np.array([0.,0.,-vy/v,r-v*kappa]);feedback=s if adaptive_feedback else 1.
    desired=feedforward-gain(scheduled,16.,feedback)@(e-target)
    nominal=ScheduledLQR(16.)(state,route)
    return float(nominal+weight*(desired-nominal))
