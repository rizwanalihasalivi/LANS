"""Single-variable revision: same inherited reward/dynamics, .08-rad residual scale."""
import importlib.util,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent
sys.path.insert(0,str(RESEARCH))
import environment
from tracking import tracking_lqr
environment.lqr=tracking_lqr
spec=importlib.util.spec_from_file_location('survival_v2_unchanged',RESEARCH/'environment-v2.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from mapping import legacy_units,RESIDUAL_SCALE_RAD

class MatchedResidualEnv(module.SurvivalEnv):
    def __init__(self,seed=0):super().__init__('residual',seed)
    def step(self,action):
        mapped=legacy_units(action)
        obs,reward,terminated,truncated,info=super().step(mapped)
        info['requested_residual_rad']=float(mapped[0])*.5
        assert abs(info['requested_residual_rad'])<=RESIDUAL_SCALE_RAD+1e-9
        return obs,reward,terminated,truncated,info
