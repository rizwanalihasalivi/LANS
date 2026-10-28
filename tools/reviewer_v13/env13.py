"""Causal recovered-controller training/evaluation; executed physical reward."""
import boot13
import math
import numpy as np
from environment import CausalEnv
from filtered import FilteredController
from control13 import SmoothController


class Env(CausalEnv):
    def __init__(self,pair=0,slot=0,seed=9701,profile='budget',case=None,scenario=None,
                 reward_kind='physical',noise_base=1906000000):
        self.profile=profile;self.override_scenario=scenario
        self.reward_kind=reward_kind;self.noise_base=noise_base
        super().__init__(pair,slot,seed,mode='lqr',case=case)

    def reset(self,**kwargs):
        _,info=super().reset(**kwargs)
        if not self.fixed_case:
            self.noise_id=self.noise_base+self.pair*1000000+self.slot*10000+self.index
            self.noise=np.random.default_rng(self.noise_id).normal(0,[.03,math.radians(.17),.01,.1],(self.horizon+1,4))
            info['noise_id']=self.noise_id
        if self.override_scenario=='poll10':self.service=.01
        if self.profile=='original':self.ctrl=FilteredController('age_original')
        elif self.profile=='oldfiltered':self.ctrl=FilteredController('age_filtered')
        else:self.ctrl=SmoothController(budget=self.profile!='lowpass',baseline_only=self.profile=='lqr')
        self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4)
        self._sense()
        return self.obs.copy(),info

    def _sense(self):
        super()._sense()
        self.ctrl.previews=self.obs[6:9].astype(float)*.02
        self.obs[14]=float(np.clip(getattr(self.ctrl,'filtered',0.)/.08,-1,1))

    def step_residual(self,residual):
        obs,reward,failed,done,row=super().step_residual(residual)
        legacy=reward
        if self.reward_kind=='physical':
            reward=-(row['lateral_error']/.5)**2-.2*(row['heading_error']/.1)**2-.2*(row['steering_rate']/.35)**2-.005*(row['command']/.5)**2-10*failed
        elif self.reward_kind!='legacy':raise ValueError('Unknown reward')
        if done and not failed:self._sense();obs=self.obs.copy()
        rates=getattr(self.ctrl,'predicted_rates',(math.nan,math.nan))
        row.update(reward=float(reward),legacy_reward=float(legacy),filtered_residual=getattr(self.ctrl,'filtered',0.),
                   projection=getattr(self.ctrl,'projection',1.),baseline_rate_prediction=rates[0],candidate_rate_prediction=rates[1])
        return obs,float(reward),failed,done,row
