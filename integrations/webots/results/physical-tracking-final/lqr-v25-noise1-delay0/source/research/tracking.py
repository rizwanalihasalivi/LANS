"""Curvature-equilibrium reference for the common speed-scheduled LQR regulator."""
import numpy as np
from core import lqr as origin_regulator

def equilibrium(speed,curvature):
    yaw_rate=speed*curvature
    lateral_velocity=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    return np.array([0.,lateral_velocity,-lateral_velocity/speed,yaw_rate])

def tracking_lqr(estimated_state,speed,curvature):
    return origin_regulator(estimated_state-equilibrium(speed,curvature),speed,curvature)
