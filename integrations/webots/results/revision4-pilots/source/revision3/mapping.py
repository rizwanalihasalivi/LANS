"""Explicit normalized residual units shared by training and both inference adapters."""
import math
import numpy as np

RESIDUAL_SCALE_RAD=.08
LEGACY_OUTPUT_SCALE_RAD=.5

def legacy_units(action):
    value=np.asarray(action)
    if not np.isfinite(value).all():raise ValueError('Nonfinite normalized residual action')
    # Existing environment/evaluator/worker interfaces multiply normalized actions by .5.
    return np.clip(value,-1.,1.)*(RESIDUAL_SCALE_RAD/LEGACY_OUTPUT_SCALE_RAD)

class RangeMappedPolicy:
    def __init__(self,policy):self.policy=policy
    def predict(self,*args,**kwargs):
        action,state=self.policy.predict(*args,**kwargs)
        return legacy_units(action),state

def map_worker_packet(packet):
    if packet is None:return None
    result=dict(packet)
    # Worker already applied its historical .5-rad convention. Undo it once.
    result['angle_rad']=float(legacy_units([packet['angle_rad']/LEGACY_OUTPUT_SCALE_RAD])[0]*LEGACY_OUTPUT_SCALE_RAD)
    return result
