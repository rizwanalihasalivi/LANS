"""
Small demo script that computes discrete LQR gains for the linearized 2-DOF,
runs a closed-loop simulation on a synthetic curvature profile (double-lane-change style),
and saves results to lqr_run_results.npz.

Usage:
    python run_baseline.py
"""
import numpy as np
from lqr_utils import c2d, bryson_q_r, discrete_lqr
from integrators import rk4_step
from controller_helpers import steering_feedforward, saturate, RateLimiter
from envs.lqr_env import LQREnv

def get_ref_curvature(t):
    """Example toy curvature: a double-lane-change style smooth bump pair."""
    # two Gaussian bumps of opposite sign
    k1 = 0.02 * np.exp(-((t - 2.0) ** 2) / 0.2)
    k2 = -0.02 * np.exp(-((t - 4.0) ** 2) / 0.2)
    return k1 + k2

def main():
    dt = 0.01
    sim_time = 6.0
    env = LQREnv(dt=dt, vx=15.0)
    A, B = env.get_continuous_matrices()
    Ad, Bd = c2d(A, B, dt)

    # Bryson rule: expected maxima (vy, r, y, psi)
    state_max = [1.5, 0.8, 0.6, 0.2]
    input_max = [0.4]
    Q, R = bryson_q_r(state_max, input_max)
    Kd, P = discrete_lqr(Ad, Bd, Q, R)

    # simulation initialization
    x = np.zeros(4)
    rate_limiter = RateLimiter(rate_limit=1.0)
    history = {"t": [], "x": [], "u": [], "kref": []}

    t = 0.0
    prev_u = 0.0
    while t < sim_time:
        # sample curvature ref
        kref = get_ref_curvature(t)
        # feedforward steering (small-angle)
        delta_ff = steering_feedforward(kref, env.wheelbase)
        # error state e = x - x_ref. For now assume x_ref = 0 (we use feedforward for curvature)
        e = x  # because x_ref is zero in error coordinates
        # discrete LQR feedback (use Kd designed for Ad,Bd)
        u_fb = -Kd.dot(e)
        u_cmd = float(delta_ff + u_fb)
        # apply rate limit + saturation
        u_cmd = rate_limiter(u_cmd, dt)
        u_cmd = saturate(u_cmd, -env.steering_limit, env.steering_limit)

        # integrate continuous dynamics
        x = rk4_step(lambda xx, uu: env.dyn(xx, uu), x, u_cmd, dt)

        history["t"].append(t)
        history["x"].append(x.copy())
        history["u"].append(u_cmd)
        history["kref"].append(kref)

        t += dt

    # save data
    np.savez("lqr_run_results.npz", t=np.array(history["t"]), x=np.array(history["x"]),
             u=np.array(history["u"]), kref=np.array(history["kref"]))
    print("Saved lqr_run_results.npz")

if __name__ == "__main__":
    main()
