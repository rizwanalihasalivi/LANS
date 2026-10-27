"""Causal forecast of PPO inputs over estimated observation-to-response delay.

This is approximate model-based response-delay compensation, not timestamp
refreshing, physical transport-delay cancellation or a safety certificate.
"""
import boot7
import math
import numpy as np
from interface4 import FreshController

PROFILE='latency_compensated_query_v7'

def forecast_state(estimate,actuator,speed,previews,gain,horizon):
    z=np.asarray(estimate,dtype=float).copy();delta=float(actuator)
    ks=np.asarray(previews,dtype=float);g=np.asarray(gain,dtype=float)
    if z.shape!=(4,) or ks.shape!=(3,) or g.shape!=(4,):raise ValueError('Invalid forecast dimensions')
    if not np.isfinite([*z,delta,speed,*ks,*g,horizon]).all() or not 0<=horizon<=.04 or speed<5:raise ValueError('Invalid forecast inputs')
    elapsed=0.
    while elapsed<horizon-1e-12:
        dt=min(.01,horizon-elapsed);k=float(np.interp(speed*elapsed,[0.,10.,20.],ks))
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*k
        target=np.array([0.,vyref,-vyref/speed,speed*k])
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*k
        command=float(np.clip(ff-g@(z-target),-.5,.5))
        delta+=dt*float(np.clip((command-delta)/.05,-.35,.35))
        ey,vy,ep,r=z
        front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        z+=dt*np.array([vy+speed*ep,(front+rear)/1650-speed*r,r-speed*k,(1.2*front-1.4*rear)/4224])
        elapsed+=dt
    shifted=np.interp(np.array([0.,10.,20.])+speed*horizon,[0.,10.,20.],ks)
    return z,delta,shifted

class DelayCompensator:
    def __init__(self):self.delay_s=.01;self.samples=0;self.last_sequence=-1
    def observe(self,sequence,response_age_s):
        if not isinstance(sequence,int) or sequence<0 or not math.isfinite(response_age_s) or response_age_s<0:raise ValueError('Invalid completed response history')
        if sequence<=self.last_sequence:return False
        self.last_sequence=sequence
        sample=min(.04,response_age_s)
        self.delay_s=.75*self.delay_s+.25*sample
        self.samples+=1
        return True
    def prepare(self,observation,estimate,actuator,speed,previews,gain):
        raw=np.asarray(observation,dtype=np.float32)
        if raw.shape!=(20,) or not np.isfinite(raw).all() or np.any(raw[[15,16,17,19]]):raise ValueError('Causal v5 physical/history features required')
        horizon=float(np.clip(self.delay_s,0.,.04))
        z,delta,ks=forecast_state(estimate,actuator,speed,previews,gain,horizon)
        result=raw.copy();used=horizon;reason='predicted_input'
        if not np.isfinite([*z,delta,*ks]).all() or abs(z[0])>1.5 or abs(z[2])>.25:
            used=0.;reason='forecast_envelope_fallback'
        elif horizon:
            ey,vy,ep,r=z
            result[:9]=[ey/3,ep/.3,(vy+speed*ep)/5,r/.5,speed/25,delta/.5,*(ks/.02)]
        metadata=dict(estimated_delay_s=horizon,used_horizon_s=used,completed_history_samples=self.samples,
            last_completed_sequence=self.last_sequence,reason=reason,raw_observation=raw.tolist(),
            model='nominal bicycle+rate-limited first-order actuator, LQR continuation; current speed/gain and preview interpolation')
        return result,metadata

class CompensatedController(FreshController):
    def __init__(self):
        super().__init__();self.policy_history_feature=True;self.compensator=DelayCompensator()
    def prepare_query(self,*args):return self.compensator.prepare(*args)
