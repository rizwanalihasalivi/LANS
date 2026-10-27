"""Correct the time-limit terminal observation used by PPO value bootstrap."""
import boot10
from env9 import Env as Previous
from controller10 import AuditedController,RKController
from features9 import make_observation,NEW
import numpy as np

class Env(Previous):
    def reset(self,**kwargs):
        _,info=super().reset(**kwargs)
        kind=AuditedController if self.source=='ppo_euler' else RKController
        self.ctrl=kind(compensated=True,baseline=self.source=='lqr')
        self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self._sense()
        return self.obs.copy(),info
    def step_residual(self,residual):
        obs,reward,failed,done,info=super().step_residual(residual)
        if done and not failed:
            # The base env skipped sensing at the horizon and returned the
            # PRE-transition input. Gymnasium/SB3 bootstraps time-limit values
            # from terminal_observation, so it must represent the next state.
            self._sense();obs=self.obs.copy()
        return obs,reward,failed,done,info
