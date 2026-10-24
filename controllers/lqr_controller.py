"""Speed/parameter scheduled continuous-time LQR with turning equilibrium."""
import numpy as np
from scipy.linalg import solve_continuous_are
from models.bicycle_model import VEHICLE_PARAMS, get_error_state_model


def get_lqr_controller(vx=25., params=None):
    if not np.isfinite(vx) or vx <= 0:
        raise ValueError('speed must be positive')
    p = dict(VEHICLE_PARAMS if params is None else params)
    A, B = get_error_state_model(vx, p)
    Q = np.diag([1., .1, 1., .1]); R = np.array([[1.]])
    gain = np.linalg.solve(R, B.T @ solve_continuous_are(A, B, Q, R)).ravel()

    def control(error_state, curvature=0.):
        length = p['lf'] + p['lr']
        vy_ref = (p['lr'] * vx - p['m'] * p['lf'] * vx**3 / (length * p['Cr'])) * curvature
        target = np.array([0., 0., -vy_ref / vx, 0.])
        feedforward = (length + p['m'] / length * (p['lr']/p['Cf'] - p['lf']/p['Cr']) * vx**2) * curvature
        return float(np.clip(feedforward - gain @ (np.asarray(error_state)-target), -.5, .5))
    return gain, control
