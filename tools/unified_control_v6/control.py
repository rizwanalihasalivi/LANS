"""Per-step nonlinear shooting, sharing identical compute between comparators."""
import numpy as np
from numba import njit
from tools.unified_control_v5.control import Controller as Previous, project, baseline_plan
from tools.unified_control_v4.kernels import rollout


@njit(cache=True)
def refine(z, initial, warm, accel, previous, dt, horizon, stiff, gains, route,
           npcs, radius, buffer, uncertainty, angle, rate, limit, feedback):
    args = (previous, dt, horizon, stiff, gains, route, npcs, radius, buffer,
            uncertainty, angle, rate, feedback)
    best = project(z, initial, accel, previous, dt, stiff, gains, route, angle, rate, limit, feedback)
    score = rollout(z, best[0], accel, *args, best)[0]
    baseline = baseline_plan(z, len(best), accel, previous, dt, stiff, gains, route, angle, rate, feedback)
    for seed in (baseline, warm):
        candidate = project(z, seed, accel, previous, dt, stiff, gains, route, angle, rate, limit, feedback)
        value = rollout(z, candidate[0], accel, *args, candidate)
        if value[1] >= 0. and value[0] < score:
            best = candidate; score = value[0]
    # Fixed finite budget, declared before training-only calibration. Each
    # actuator knot can vary independently rather than sharing a five-tick block.
    for amplitude in (.01, .0025, .000625):
        for index in range(len(best)):
            chosen = best.copy(); value = score
            for sign in (-1., 1.):
                trial = best.copy(); trial[index] += sign * amplitude
                trial = project(z, trial, accel, previous, dt, stiff, gains, route, angle, rate, limit, feedback)
                result = rollout(z, trial[0], accel, *args, trial)
                if result[1] >= 0. and result[0] < value - 1e-10:
                    chosen = trial; value = result[0]
            best = chosen; score = value
    return best


class Planner:
    def __init__(self, owner, linear):
        self.owner = owner; self.linear = linear; self.warm = None; self.used_backup = False
    @property
    def status(self):
        return ('NONLINEAR_BACKUP_FROM_' if self.used_backup else '') + self.linear.status
    @property
    def failures(self):
        return self.linear.failures
    def plan(self, state, route, previous, cfg, stiffness, penalty):
        initial = self.linear.plan(state, route, previous, cfg, stiffness, penalty)
        self.used_backup = initial is None
        c = self.owner; now = c._decision_now; old = c.supervisor.state
        risk = c.supervisor.assess(state, c.inbox, c.expected, now, now + c.delay)
        c.supervisor.state = old
        accel = c.supervisor.acceleration(float(np.clip(.8 * (c.target_speed - state[3]), -cfg.max_brake, cfg.max_accel)), risk)
        npcs = np.array([[*other, unc] for _, other, unc in risk.vehicles], float).reshape(-1, 7)
        center = c.stiffness_estimate if c.adaptive else 1.
        if initial is None:
            initial = baseline_plan(state, round(cfg.horizon / cfg.dt), accel, previous,
                                    cfg.dt, center, c._gains, c._route, cfg.steering_limit,
                                    cfg.steering_rate, c.feedback_stiffness)
        warm = initial if self.warm is None else self.warm
        plan = refine(state, initial, warm, accel, previous, cfg.dt, cfg.horizon, center,
                      c._gains, c._route, npcs, cfg.vehicle_radius, cfg.buffer,
                      cfg.uncertainty_rate, cfg.steering_limit, cfg.steering_rate,
                      cfg.residual_limit, c.feedback_stiffness)
        self.warm = np.r_[plan[1:], plan[-1]]
        return plan


class Controller(Previous):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.planner is not None:
            self.planner = Planner(self, self.planner.linear)
