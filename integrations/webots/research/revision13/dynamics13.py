"""Original observation contract on explicit scaled and reflected path geometry.

path6 = (kind, amplitude, wavelength, phase, longitudinal_scale, lateral_sign).
No plant parameter or future measurement is added to the student interface.
"""
from pathlib import Path
import sys

_RESEARCH = Path(__file__).resolve().parents[1]
_V8 = str(_RESEARCH / 'revision8')
if _V8 not in sys.path:
    sys.path.insert(0, _V8)
import bootstrap  # noqa: F401
import math
import numpy as np
from numba import njit
from core import reference


@njit(cache=True)
def path_values13(x, path):
    kind, amplitude, wavelength, phase, scale, sign = path
    if not math.isfinite(scale) or scale <= 0. or sign not in (-1., 1.):
        raise ValueError('positive finite path scale and reflection sign +/-1 required')
    y, d, dd = reference(x / scale, kind, amplitude, wavelength, phase)
    y *= sign
    d *= sign / scale
    dd *= sign / (scale * scale)
    return y, math.atan(d), dd / (1 + d * d)**1.5


@njit(cache=True)
def measure13(state, speed, path, noise, delay, estimate, cov, previous_raw, first, noise_scale):
    """Exact revision7 estimator operations; only the path lookup changes."""
    y, heading, curvature = path_values13(state[0], path)
    raw = np.array([state[1] - y, state[2] - heading, state[4], speed]) + noise
    z = previous_raw.copy() if delay and not first else raw.copy()
    v = max(5., z[3]); cf = cr = 80000.; m = 1650.; iz = 4224.; lf = 1.2; lr = 1.4
    a = np.array([[0., 1., v, 0.], [0., -(cf + cr) / (m * v), 0., (cr * lr - cf * lf) / (m * v) - v],
                  [0., 0., 0., 1.], [0., (cr * lr - cf * lf) / (iz * v), 0., -(cf * lf * lf + cr * lr * lr) / (iz * v)]])
    ad = np.eye(4) + .01 * a; b = .01 * np.array([0., cf / m, 0., cf * lf / iz])
    prediction = np.array([z[0], 0., z[1], z[2]]) if first else ad @ estimate + b * state[5] + np.array([0., 0., -v * curvature * .01, 0.])
    updated_cov = ad @ cov @ ad.T + np.diag(np.array([1e-7, 1e-4, 1e-8, 1e-5]))
    h = np.array([[1., 0., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]])
    variances = np.array([.03, math.radians(.17), .01])**2 * max(noise_scale, .01)**2
    innovation = h @ updated_cov @ h.T + np.diag(variances)
    kalman = np.linalg.solve(innovation, (updated_cov @ h.T).T).T
    prediction += kalman @ (z[:3] - h @ prediction)
    updated_cov = (np.eye(4) - kalman @ h) @ updated_cov
    measured = max(5., np.float64(np.float32(v / 25)) * 25)
    return prediction, updated_cov, raw, measured, curvature


@njit(cache=True)
def features13(state, estimate, raw_speed, path, executor, tick, service):
    """Original twenty observed/history features with transformed path previews."""
    ey, vy, ep, r = estimate; t = tick * .01; packet = executor[3] >= 0; pending = executor[7] >= 0
    preview = np.array([path_values13(state[0] + d, path)[2] for d in (0., 10., 20.)])
    return np.array([ey / 3, ep / .3, (vy + raw_speed * ep) / 5, r / .5, raw_speed / 25, state[5] / .5,
        preview[0] / .02, preview[1] / .02, preview[2] / .02,
        executor[0], min(executor[1], 3.) / 3., executor[5] / .08 if packet else 0.,
        (t - executor[4]) / .1 if packet else 0., 1. if packet else 0.,
        executor[9] / .08 if pending else 0., max(0., executor[6] - t) / .1 if pending else 0.,
        (t - executor[8]) / .1 if pending else 0., 1. if pending else 0., executor[11] / .5, service / 10.], dtype=np.float32)
