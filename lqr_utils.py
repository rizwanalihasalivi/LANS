import numpy as np
from scipy.linalg import solve_continuous_are, solve_discrete_are
from scipy.signal import cont2discrete

def continuous_lqr(A, B, Q, R):
    """
    Continuous-time LQR: returns K such that u = -K x (continuous design).
    """
    P = solve_continuous_are(A, B, Q, R)
    K = np.linalg.inv(R) @ (B.T @ P)
    return K, P

def discrete_lqr(A, B, Q, R):
    """
    Discrete-time LQR (assumes A,B are discrete).
    Returns K and solution P of discrete Riccati.
    """
    P = solve_discrete_are(A, B, Q, R)
    K = np.linalg.inv(B.T @ P @ B + R) @ (B.T @ P @ A)
    return K, P

def c2d(A, B, dt):
    """
    Zero-order hold discretization returning (Ad, Bd).
    """
    # cont2discrete expects (A,B,C,D)
    C = np.zeros((A.shape[0], 0))
    D = np.zeros((0, 0))
    Ad, Bd, _, _, _ = cont2discrete((A, B, C, D), dt, method='zoh')
    return Ad, Bd

def bryson_q_r(state_max, input_max, eps=1e-6):
    """
    Build diagonal Q and R using Bryson's rule from expected maxima.
    state_max: iterable (len = n_states)
    input_max: iterable (len = n_inputs)
    """
    Q = np.diag([1.0 / (max(abs(s), eps) ** 2) for s in state_max])
    R = np.diag([1.0 / (max(abs(u), eps) ** 2) for u in input_max])
    return Q, R
