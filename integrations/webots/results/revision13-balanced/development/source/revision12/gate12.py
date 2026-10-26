"""Controlled gate ablation: original, preview geometry, or lateral objective.

Previews are three physical curvatures (1/m), decoded from the actor's existing
float32 observation channels at0/10/20m. The local curvature argument anchors
point0, preserving the original baseline input. No true plant parameter or
future sensor-noise input enters this interface.
"""
from pathlib import Path
import sys

_RESEARCH = Path(__file__).resolve().parents[1]
_V8 = str(_RESEARCH / 'revision8')
if _V8 not in sys.path:
    sys.path.insert(0, _V8)
import bootstrap  # noqa: F401 — installs the original research module paths
import math
import numpy as np
from numba import njit
from gating import predict_cost
from kernels import execution_step, reset_gate


@njit(cache=True)
def _curvature_at(distance, curvature, previews):
    if distance <= 0.:
        return curvature
    if distance < 10.:
        return curvature + (previews[1] - curvature) * (distance / 10.)
    if distance < 20.:
        return previews[1] + (previews[2] - previews[1]) * ((distance - 10.) / 10.)
    return previews[2]


@njit(cache=True)
def cost12(estimate, actuator, command, speed, curvature, gain, previews, variant):
    """Twenty10ms prediction steps; variant0 delegates the archived predictor."""
    if variant == 0:
        return predict_cost(estimate, actuator, command, speed, curvature, gain, 20)
    if variant != 1 and variant != 2:
        raise ValueError('variant must be0=legacy,1=preview,2=lateral')
    z = estimate.copy()
    delta = actuator
    cost = 0.
    for i in range(20):
        k = _curvature_at(speed * i * .01, curvature, previews) if variant == 1 else curvature
        vyref = (1.4 * speed - 1650 * 1.2 * speed**3 / (2.6 * 80000)) * k
        target = np.array([0., vyref, -vyref / speed, speed * k])
        ff = (2.6 + 1650 / 2.6 * (1.4 / 80000 - 1.2 / 80000) * speed**2) * k
        u = command if i < 5 else max(-.5, min(.5, ff - np.dot(gain, z - target)))
        delta += .01 * max(-.35, min(.35, (u - delta) / .05))
        ey, vy, ep, r = z
        front = 80000 * (delta - (vy + 1.2 * r) / speed)
        rear = 80000 * (-(vy - 1.4 * r) / speed)
        z = z + .01 * np.array([vy + speed * ep, (front + rear) / 1650 - speed * r,
                                r - speed * k, (1.2 * front - 1.4 * rear) / 4224])
        if variant == 2:
            cost += .01 * (z[0] / .5)**2
        else:
            # State/cost are evaluated at the end of the integration step.
            cost_k = _curvature_at(speed * (i + 1) * .01, curvature, previews)
            cost += .01 * ((z[0] / .5)**2 + .2 * (z[2] / .1)**2
                          + .01 * ((z[3] - speed * cost_k) / .2)**2 + .001 * (u / .5)**2)
    if variant == 2:
        return cost + .1 * (z[0] / .5)**2
    return cost + .1 * ((z[0] / .5)**2 + .2 * (z[2] / .1)**2)


@njit(cache=True)
def _gate12(executor, t, baseline, estimate, actuator, speed, curvature, gain, previews, variant):
    # Frozen rejection, persistence, freshness, candidate and blend rules.
    if executor[3] < 0:
        return reset_gate(executor, baseline, 0)
    if (not np.isfinite(np.array([t, baseline, executor[4], executor[5], actuator, speed, curvature])).all()
            or not np.isfinite(estimate).all()
            or (variant == 1 and not np.isfinite(previews).all())):
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
    j0 = cost12(estimate, actuator, baseline, speed, curvature, gain, previews, variant)
    best = j0
    weight = 0.
    command = baseline
    for limit in (.1, .25, .5):
        w = min(limit * fresh, executor[0] + .05)
        u = (1 - w) * baseline + w * candidate
        value = cost12(estimate, actuator, u, speed, curvature, gain, previews, variant)
        if value < best:
            best = value
            weight = w
            command = u
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
def execution_step12(executor, t, proposal, service, baseline, estimate, actuator,
                     speed, curvature, gain, previews, variant, submit_request=True):
    """Original executor state and return contract; variants change only scoring."""
    if variant == 0:
        return execution_step(executor, t, proposal, service, baseline, estimate, actuator,
                              speed, curvature, gain, False, submit_request)
    if variant != 1 and variant != 2:
        raise ValueError('variant must be0=legacy,1=preview,2=lateral')
    if executor[7] >= 0 and executor[6] <= t + 1e-9:
        executor[3] = executor[7]
        executor[4] = executor[8]
        executor[5] = executor[9]
        executor[7] = -1.
    submitted = executor[7] < 0 and submit_request
    if submitted:
        executor[10] += 1
        if service == 0:
            executor[3] = executor[10]
            executor[4] = t
            executor[5] = max(-.08, min(.08, proposal))
        else:
            executor[6] = t + service * .01
            executor[7] = executor[10]
            executor[8] = t
            executor[9] = max(-.08, min(.08, proposal))
    command, weight, reason, _, _ = _gate12(executor, t, baseline, estimate, actuator,
                                           speed, curvature, gain, previews, variant)
    executor[11] = command
    return command, weight, reason, submitted
