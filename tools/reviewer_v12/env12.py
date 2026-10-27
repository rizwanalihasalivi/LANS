"""Forecast fix with unchanged actor schema, plant, reward and baseline."""
import boot12
import numpy as np
from env11 import Env as Previous
from forecast12 import Controller


class Env(Previous):
    def __init__(self, *args, training_noise_base=1806000000, **kwargs):
        self.training_noise_base = training_noise_base
        super().__init__(*args, **kwargs)

    def reset(self, **kwargs):
        _, info = super().reset(**kwargs)
        if not self.fixed_case:
            import math
            self.noise_id = self.training_noise_base+self.pair*1000000+self.slot*10000+self.index
            self.noise = np.random.default_rng(self.noise_id).normal(
                0, [.03, math.radians(.17), .01, .1], (self.horizon+1, 4))
            info['noise_id'] = self.noise_id
        self.ctrl = Controller(compensated=True, baseline=self.source == 'lqr')
        self.estimate = np.zeros(4)
        self.cov = np.eye(4)*.01
        self.previous = np.zeros(4)
        self._sense()
        return self.obs.copy(), info

