"""Numerically consistent causal forecast; unchanged nominal model/50ms age rule."""
import boot12
import math
import numpy as np
from numba import njit
from compensation import DelayCompensator
from rollout10 import micro_step, curvature_at
from controller10 import RKController


@njit(cache=True)
def integrate(z, actuator, speed, ks, gain, horizon):
    state = (z[0], z[1], z[2], z[3], actuator)
    elapsed = 0.
    while elapsed < horizon - 1e-12:
        tick_end = min(horizon, elapsed + .01)
        k = curvature_at(elapsed, speed, ks)
        vyref = (1.4*speed - 1650*1.2*speed**3/(2.6*80000))*k
        ff = (2.6 + 1650/2.6*(1.4/80000-1.2/80000)*speed**2)*k
        feedback = (gain[0]*state[0] + gain[1]*(state[1]-vyref)
                    + gain[2]*(state[2]+vyref/speed) + gain[3]*(state[3]-speed*k))
        command = max(-.5, min(.5, ff-feedback))
        while elapsed < tick_end - 1e-12:
            dt = min(.001, tick_end-elapsed)
            state = micro_step(state, command, speed, ks, elapsed, dt)
            elapsed += dt
    return state


def forecast_state(estimate, actuator, speed, previews, gain, horizon):
    z = np.asarray(estimate, dtype=float)
    ks = np.asarray(previews, dtype=float)
    g = np.asarray(gain, dtype=float)
    if z.shape != (4,) or ks.shape != (3,) or g.shape != (4,):
        raise ValueError('Invalid forecast dimensions')
    if (not np.isfinite([*z, actuator, speed, *ks, *g, horizon]).all()
            or not 0 <= horizon <= .04 or speed < 5 or abs(actuator) > .5):
        raise ValueError('Invalid forecast inputs')
    value = np.array(integrate(z, float(actuator), float(speed), ks, g, float(horizon)))
    shifted = np.interp(np.array([0., 10., 20.])+speed*horizon, [0., 10., 20.], ks)
    return value[:4], float(value[4]), shifted


class Compensator(DelayCompensator):
    def prepare(self, observation, estimate, actuator, speed, previews, gain):
        raw = np.asarray(observation, dtype=np.float32)
        if raw.shape != (20,) or not np.isfinite(raw).all() or np.any(raw[[15, 16, 17, 19]]):
            raise ValueError('Causal v5 physical/history features required')
        horizon = float(np.clip(self.delay_s, 0., .04))
        z, delta, ks = forecast_state(estimate, actuator, speed, previews, gain, horizon)
        result = raw.copy()
        used, reason = horizon, 'predicted_input'
        if not np.isfinite([*z, delta, *ks]).all() or abs(z[0]) > 1.5 or abs(z[2]) > .25:
            used, reason = 0., 'forecast_envelope_fallback'
        elif horizon:
            ey, vy, ep, r = z
            result[:9] = [ey/3, ep/.3, (vy+speed*ep)/5, r/.5, speed/25, delta/.5, *(ks/.02)]
        return result, dict(estimated_delay_s=horizon, used_horizon_s=used,
                           completed_history_samples=self.samples, last_completed_sequence=self.last_sequence,
                           reason=reason, raw_observation=raw.tolist(),
                           model='nominal bicycle + rate-limited actuator; 1ms RK4; held 10ms LQR; current speed/gain and preview')


class Controller(RKController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.compensator = Compensator()

