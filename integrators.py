import numpy as np

def rk4_step(f, x, u, dt, params=None):
    """
    One RK4 step for dx/dt = f(x, u, params).
    f should return a numpy array of the same shape as x.
    """
    if params is None:
        k1 = f(x, u)
        k2 = f(x + 0.5 * dt * k1, u)
        k3 = f(x + 0.5 * dt * k2, u)
        k4 = f(x + dt * k3, u)
    else:
        k1 = f(x, u, params)
        k2 = f(x + 0.5 * dt * k1, u, params)
        k3 = f(x + 0.5 * dt * k2, u, params)
        k4 = f(x + dt * k3, u, params)
    return x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
