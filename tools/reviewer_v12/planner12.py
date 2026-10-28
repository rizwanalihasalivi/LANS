"""Same nonlearned proposal search, using the corrected causal forecast too."""
import boot12
import copy
import math
from forecast12 import forecast_state
from kernels import lqr


def propose(ctrl, estimate, actuator, speed, previews, gain, gains, t):
    delay = ctrl.compensator.delay_s
    z, delta, ks = forecast_state(estimate, actuator, speed, previews, gain, delay)
    base, scheduled = lqr(z, speed, ks[0], gains)
    candidates = []
    for residual in (-.08, -.04, 0., .04, .08):
        candidate = copy.copy(ctrl)
        candidate.previews = ks.copy()
        candidate.packet = (ctrl.sequence+1, t, residual)
        _, reason = candidate.choose(t+delay, base, z, delta, speed, ks[0], scheduled)
        _, cost = candidate.last_costs
        eligible = reason in ('accepted', 'recovery') and math.isfinite(cost)
        candidates.append((cost if eligible else math.inf, abs(residual), residual))
    best = min(candidates)
    return best[2] if math.isfinite(best[0]) else 0.

