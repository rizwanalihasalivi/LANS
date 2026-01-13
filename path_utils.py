import numpy as np
from scipy.interpolate import CubicSpline

def smooth_path_xy(x, y):
    """
    Fit cubic splines parameterized by arc-length s.
    Returns (cs_x, cs_y, s_end).
    """
    x = np.asarray(x)
    y = np.asarray(y)
    dx = np.diff(x)
    dy = np.diff(y)
    ds = np.hypot(dx, dy)
    s = np.concatenate(([0.0], np.cumsum(ds)))
    cs_x = CubicSpline(s, x)
    cs_y = CubicSpline(s, y)
    return cs_x, cs_y, s[-1]

def sample_path(cs_x, cs_y, s_end, n=1000):
    """
    Sample the path at n points uniformly in arc-length and return dictionary:
    {s, x, y, curvature, yaw}
    """
    s = np.linspace(0, s_end, n)
    x = cs_x(s)
    y = cs_y(s)
    dxds = cs_x.derivative(1)(s)
    dyds = cs_y.derivative(1)(s)
    ddxds = cs_x.derivative(2)(s)
    ddyds = cs_y.derivative(2)(s)
    yaw = np.arctan2(dyds, dxds)
    curvature = (dxds * ddyds - dyds * ddxds) / ((dxds ** 2 + dyds ** 2) ** 1.5)
    return dict(s=s, x=x, y=y, curvature=curvature, yaw=yaw)
