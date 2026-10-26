"""Frozen gate lifecycle with declared heading/actuator-rate objective variants.

0: legacy combined cost; 1: revision12 lateral-only cost;
2/3/4: heading/rate weights (.05,.01), (.10,.03), (.20,.10).
All models retain nominal constant-curvature dynamics and the original horizon.
"""
from pathlib import Path
import sys

_RESEARCH = Path(__file__).resolve().parents[1]
for _folder in ('revision8', 'revision12'):
    _path = str(_RESEARCH / _folder)
    if _path not in sys.path:
        sys.path.insert(0, _path)
import bootstrap  # noqa: F401
import math
import numpy as np
from numba import njit
from gating import predict_cost
from gate12 import cost12, execution_step12
from kernels import execution_step, reset_gate


@njit(cache=True)
def objective_weights13(variant):
    if variant == 2:
        return .05, .01
    if variant == 3:
        return .10, .03
    if variant == 4:
        return .20, .10
    raise ValueError('balanced variants are 2, 3, 4')


@njit(cache=True)
def cost13(estimate, actuator, command, speed, curvature, gain, variant):
    if variant == 0:
        return predict_cost(estimate, actuator, command, speed, curvature, gain, 20)
    if variant == 1:
        return cost12(estimate, actuator, command, speed, curvature, gain, np.zeros(3), 2)
    heading_weight, rate_weight = objective_weights13(variant)
    z = estimate.copy(); delta = actuator; cost = 0.
    vyref = (1.4 * speed - 1650 * 1.2 * speed**3 / (2.6 * 80000)) * curvature
    target = np.array([0., vyref, -vyref / speed, speed * curvature])
    ff = (2.6 + 1650 / 2.6 * (1.4 / 80000 - 1.2 / 80000) * speed**2) * curvature
    for i in range(20):
        u = command if i < 5 else max(-.5, min(.5, ff - np.dot(gain, z - target)))
        # Penalize physical predicted motion, including the first step from
        # the current actuator, not a difference between hypothetical commands.
        rate = max(-.35, min(.35, (u - delta) / .05))
        delta += .01 * rate
        ey, vy, ep, r = z
        front = 80000 * (delta - (vy + 1.2 * r) / speed)
        rear = 80000 * (-(vy - 1.4 * r) / speed)
        z = z + .01 * np.array([vy + speed * ep, (front + rear) / 1650 - speed * r,
                                r - speed * curvature, (1.2 * front - 1.4 * rear) / 4224])
        cost += .01 * ((z[0] / .5)**2 + heading_weight * (z[2] / .1)**2 + rate_weight * (rate / .35)**2)
    return cost + .1 * ((z[0] / .5)**2 + heading_weight * (z[2] / .1)**2)


@njit(cache=True)
def _gate13(executor, t, baseline, estimate, actuator, speed, curvature, gain, variant):
    if executor[3] < 0:
        return reset_gate(executor, baseline, 0)
    if (not np.isfinite(np.array([t, baseline, executor[4], executor[5], actuator, speed, curvature])).all()
            or not np.isfinite(estimate).all()):
        return reset_gate(executor, baseline, 7)
    age = t - executor[4]
    if age < 0 or age >= .05:
        return reset_gate(executor, baseline, 1)
    if executor[3] < executor[2]:
        return reset_gate(executor, baseline, 2)
    executor[2] = executor[3]
    if abs(estimate[0]) > 1.5 or abs(estimate[2]) > .25:
        return reset_gate(executor, baseline, 3)
    candidate = max(-.5, min(.5, baseline + max(-.08, min(.08, executor[5]))))
    fresh = max(0., min(1., (.05 - age) / .04))
    j0 = cost13(estimate, actuator, baseline, speed, curvature, gain, variant)
    best = j0; weight = 0.; command = baseline
    for limit in (.1, .25, .5):
        w = min(limit * fresh, executor[0] + .05)
        u = (1 - w) * baseline + w * candidate
        value = cost13(estimate, actuator, u, speed, curvature, gain, variant)
        if value < best:
            best = value; weight = w; command = u
    if not math.isfinite(j0) or not math.isfinite(best):
        return reset_gate(executor, baseline, 8, j0, best)
    if weight == 0 or j0 - best < max(1e-7, .01 * j0):
        return reset_gate(executor, baseline, 4, j0, best)
    executor[1] += 1
    if executor[1] < 3:
        executor[0] = 0.
        return baseline, 0., 5, j0, best
    executor[0] = weight
    return command, weight, 6, j0, best


@njit(cache=True)
def execution_step13(executor, t, proposal, service, baseline, estimate, actuator,
                     speed, curvature, gain, variant, submit_request=True):
    if variant == 0:
        return execution_step(executor, t, proposal, service, baseline, estimate, actuator,
                              speed, curvature, gain, False, submit_request)
    if variant == 1:
        return execution_step12(executor, t, proposal, service, baseline, estimate, actuator,
                                speed, curvature, gain, np.zeros(3), 2, submit_request)
    if variant not in (2, 3, 4):
        raise ValueError('gate variant must be integer 0..4')
    if executor[7] >= 0 and executor[6] <= t + 1e-9:
        executor[3] = executor[7]; executor[4] = executor[8]; executor[5] = executor[9]
        executor[7] = -1.
    submitted = executor[7] < 0 and submit_request
    if submitted:
        executor[10] += 1
        if service == 0:
            executor[3] = executor[10]; executor[4] = t
            executor[5] = max(-.08, min(.08, proposal))
        else:
            executor[6] = t + service * .01; executor[7] = executor[10]
            executor[8] = t; executor[9] = max(-.08, min(.08, proposal))
    command, weight, reason, _, _ = _gate13(executor, t, baseline, estimate, actuator,
                                           speed, curvature, gain, variant)
    executor[11] = command
    return command, weight, reason, submitted
