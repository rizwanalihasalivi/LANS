"""Distinct-proposal recovery across bounded stale gaps; never stale authority."""
import boot8
import math
import numpy as np
from interface4 import FreshController
from expiry_cost8 import expiry_cost
from compensation import DelayCompensator

class RecoveryController(FreshController):
    def __init__(self,compensated=False):
        super().__init__();self.policy_history_feature=True
        self.last_qualified_sequence=-1;self.last_qualified_time=None
        if compensated:self.compensator=DelayCompensator()
    def prepare_query(self,*args):return self.compensator.prepare(*args)
    def revoke(self,baseline,reason,clear=True):
        self.weight=0.;self.last_command=float(baseline);self.last_costs=(math.nan,math.nan)
        if clear:
            self.filtered=0.;self.good=0;self.last_qualified_sequence=-1;self.last_qualified_time=None
        return float(baseline),reason
    def choose(self,t,baseline,estimate,actuator,speed,curvature,gain):
        self.last_costs=(math.nan,math.nan)
        if self.last_qualified_time is not None and t-self.last_qualified_time>.05+1e-12:
            self.revoke(baseline,'recovery_expired')
        if self.packet is None:return self.revoke(baseline,'missing')
        seq,observed,residual=self.packet;age=t-observed
        if np.asarray(estimate).shape!=(4,) or np.asarray(gain).shape!=(4,) or np.asarray(self.previews).shape!=(3,):return self.revoke(baseline,'dimensions')
        if not np.isfinite([t,baseline,observed,residual,actuator,speed,curvature,*estimate,*gain,*self.previews]).all():return self.revoke(baseline,'nonfinite')
        if age<0:return self.revoke(baseline,'future')
        if seq<self.last_sequence:return self.revoke(baseline,'sequence')
        if abs(residual)>.08+1e-9:return self.revoke(baseline,'residual_bound')
        if age>=.05-1e-12:
            # Preserve only internal recovery/filter memory within the bounded
            # liveness window. Authority is immediately ZERO on every stale tick.
            return self.revoke(baseline,'age',clear=self.last_qualified_time is None)
        self.last_sequence=seq
        if abs(estimate[0])>1.5 or abs(estimate[2])>.25:return self.revoke(baseline,'envelope')
        residual=float(np.clip(residual,-.08,.08));self.filtered+=(1-math.exp(-.01/.3))*(residual-self.filtered)
        weight=min(.25,self.weight+.05);ks=self.previews.copy();ks[0]=curvature
        steps=max(0,min(100,math.ceil((.05-age-1e-12)/.01)))
        base=expiry_cost(estimate,actuator,speed,ks,gain,self.filtered,residual,0.,0)
        candidate=expiry_cost(estimate,actuator,speed,ks,gain,self.filtered,residual,weight,steps)
        self.last_costs=(base,candidate)
        if not np.isfinite([base,candidate]).all():return self.revoke(baseline,'prediction_invalid')
        if base-candidate<max(1e-7,.001*base):
            self.weight=0.;self.good=0;self.last_command=float(baseline);self.last_qualified_sequence=-1;self.last_qualified_time=None
            return float(baseline),'cost'
        if seq>self.last_qualified_sequence:
            self.good+=1;self.last_qualified_sequence=seq;self.last_qualified_time=t
        if self.good<3:
            self.weight=0.;self.last_command=float(baseline)
            return float(baseline),'recovery'
        self.weight=weight;self.last_command=float(np.clip(baseline+weight*self.filtered,-.5,.5))
        return self.last_command,'accepted'
