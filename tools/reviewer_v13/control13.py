"""Recovered latency gain with causal smoothing and local actuator-rate projection.

This bounds a one-tick NOMINAL actuator prediction relative to the current LQR
command. It does not guarantee the whole-episode RMS relative to an independent
LQR trajectory, and it is not a vehicle safety certificate.
"""
import boot13
import math
import numbers
import numpy as np
from numba import njit
from supervisor import Controller


@njit(cache=True)
def actuator_next(delta, command, dt=.01):
    distance=command-delta; sign=1. if distance>=0 else -1.; distance=abs(distance)
    tau=.05; rate=.35; transition=rate*tau
    if distance<=transition:
        movement=distance*(1-math.exp(-dt/tau))
    else:
        linear_time=(distance-transition)/rate
        if dt<=linear_time:movement=rate*dt
        else:movement=distance-transition*math.exp(-(dt-linear_time)/tau)
    return delta+sign*movement


@njit(cache=True)
def project(delta, baseline, desired):
    original=actuator_next(delta,baseline)
    limit=min(.35,1.02*abs(original-delta)/.01)
    target=actuator_next(delta,desired)
    if abs(target-delta)<=limit*.01+1e-15:
        return desired,1.,abs(original-delta)/.01,abs(target-delta)/.01
    # Search the baseline-to-candidate segment. Baseline is feasible by
    # construction, even when actuator input clipping or slew saturation binds.
    low=0.;high=1.
    for _ in range(32):
        middle=(low+high)/2
        value=baseline+middle*(desired-baseline)
        if abs(actuator_next(delta,value)-delta)<=limit*.01:low=middle
        else:high=middle
    value=baseline+low*(desired-baseline)
    return value,low,abs(original-delta)/.01,abs(actuator_next(delta,value)-delta)/.01


class SmoothController(Controller):
    def __init__(self, budget=True, baseline_only=False):
        super().__init__('latency')
        self.budget=budget;self.baseline_only=baseline_only
        self.filtered=0.;self.identity=None;self.predicted_rates=(math.nan,math.nan)
        self.projection=1.;self.previews=np.zeros(3)

    def submit(self,t,residual,service):
        if not np.isfinite([t,residual,service]).all() or t<0 or service<0 or abs(residual)>.08+1e-9:
            raise ValueError('Invalid request timestamp, delay or residual')
        return super().submit(t,residual,service)

    def revoke(self,baseline,reason):
        self.weight=0.;self.good=0;self.filtered=0.;self.last_command=float(baseline)
        return float(baseline),reason

    def choose(self,t,baseline,estimate,actuator,speed,curvature,gain):
        self.predicted_rates=(math.nan,math.nan);self.projection=1.
        if not math.isfinite(baseline) or abs(baseline)>.5+1e-9:raise ValueError('Invalid LQR baseline')
        if self.baseline_only:return self.revoke(baseline,'baseline')
        if self.packet is None:return self.revoke(baseline,'missing')
        try:seq,stamp,residual=self.packet
        except (ValueError,TypeError):return self.revoke(baseline,'packet')
        if isinstance(seq,(bool,np.bool_)) or not isinstance(seq,numbers.Integral) or seq<1:
            return self.revoke(baseline,'identity')
        if np.asarray(estimate).shape!=(4,):return self.revoke(baseline,'dimensions')
        values=[t,stamp,residual,actuator,speed,curvature,*estimate]
        if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,numbers.Real) for v in values):return self.revoke(baseline,'malformed')
        if not np.isfinite(values).all():return self.revoke(baseline,'nonfinite')
        if self.identity is not None:
            old,oldstamp,oldres=self.identity
            if seq<old or (seq==old and (stamp!=oldstamp or residual!=oldres)):return self.revoke(baseline,'identity')
        age=t-stamp
        if stamp<0 or age<0 or age>=.05-1e-12:return self.revoke(baseline,'age')
        if abs(residual)>.08+1e-9:return self.revoke(baseline,'residual')
        if speed<5 or abs(actuator)>.5 or abs(estimate[0])>1.5 or abs(estimate[2])>.25:
            return self.revoke(baseline,'envelope')
        self.identity=(int(seq),stamp,residual)
        self.last_sequence=seq
        self.filtered+=(1-math.exp(-.01/.15))*(residual-self.filtered)
        weight=.5*math.exp(-.8*max(0.,age*1000-5.))
        desired=float(np.clip(baseline+weight*self.filtered,-.5,.5))
        command=desired
        if self.budget:
            command,scale,old_rate,new_rate=project(actuator,baseline,desired)
            self.projection=scale;self.predicted_rates=(old_rate,new_rate)
            weight*=scale
        self.weight=float(weight);self.last_command=float(command)
        return float(command),'rate_projected' if self.budget and self.projection<1. else 'smoothed'
