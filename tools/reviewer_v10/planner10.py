"""Causal nominal proposal planner: strong nonlearned headroom comparator.
Uses only estimated state, measured actuator/speed, reference preview and PAST
response history. Never sees true friction/state, future noise or service wait.
"""
import boot10
import copy
import math
import numpy as np
from compensation import forecast_state
from kernels import lqr

def propose(ctrl,estimate,actuator,speed,previews,gain,gains,t):
    delay=ctrl.compensator.delay_s
    z,delta,ks=forecast_state(estimate,actuator,speed,previews,gain,delay)
    base,scheduled=lqr(z,speed,ks[0],gains)
    candidates=[]
    for residual in (-.08,-.04,0.,.04,.08):
        c=copy.copy(ctrl);c.previews=ks.copy();c.packet=(ctrl.sequence+1,t,residual)
        _,reason=c.choose(t+delay,base,z,delta,speed,ks[0],scheduled)
        j0,j1=c.last_costs
        # Favor prospective qualifying proposals even during recovery; the
        # actual gate still decides, using actual arrival age and current state.
        eligible=reason in ('accepted','recovery') and math.isfinite(j1)
        candidates.append((j1 if eligible else math.inf,abs(residual),residual))
    best=min(candidates)
    return best[2] if math.isfinite(best[0]) else 0.
