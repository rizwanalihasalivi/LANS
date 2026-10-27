"""Separately versioned, causal recovery state; no future-service features."""
import boot9
import numpy as np
from supervisor import observation as legacy_observation
from recovery8 import RecoveryController
from compensation import DelayCompensator
PROFILE='causal_recovery_history_v9'
NEW=(14,15,19)

def make_observation(state,estimate,speed,previews,ctrl,t):
    x=legacy_observation(state,estimate,speed,previews,ctrl,t)
    x[14]=np.clip(getattr(ctrl,'filtered',0.)/.08,-1,1)
    x[15]=ctrl.compensator.delay_s/.04
    previous=getattr(ctrl,'last_qualified_time',None)
    if previous is not None and previous>t+1e-9:raise ValueError('Future qualification history is not causal')
    x[19]=1. if previous is None else np.clip((t-previous)/.05,0,1)
    return x

class QueryController(RecoveryController):
    def __init__(self,compensated=True,baseline=False):
        super().__init__(compensated=True);self.compensated=compensated;self.baseline_only=baseline
    def choose(self,*args):
        if self.baseline_only:return self.revoke(args[1],'baseline')
        return super().choose(*args)
    def prepare_query(self,raw,*args):
        raw=np.asarray(raw,np.float32)
        if raw.shape!=(20,) or not np.isfinite(raw).all() or np.any(raw[[16,17]]):raise ValueError('v9 causal recovery features required')
        if self.compensated:
            legacy=raw.copy();legacy[[15,19]]=0
            result,meta=self.compensator.prepare(legacy,*args)
            result[[15,19]]=raw[[15,19]];meta['raw_observation']=raw.tolist()
        else:
            result=raw.copy();meta=dict(estimated_delay_s=self.compensator.delay_s,used_horizon_s=0.,completed_history_samples=self.compensator.samples,last_completed_sequence=self.compensator.last_sequence,reason='raw_input',raw_observation=raw.tolist())
        return result,meta
