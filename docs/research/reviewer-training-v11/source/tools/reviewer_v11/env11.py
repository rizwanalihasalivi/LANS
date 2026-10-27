"""Corrected v10 training environment with a genuinely fresh training namespace."""
import boot11
import math
import json
import numpy as np
from env10 import Env as Corrected
P=json.loads((boot11.HERE/'protocol.json').read_text())
class Env(Corrected):
    def reset(self,**kwargs):
        _,info=super().reset(**kwargs)
        if not self.fixed_case:
            self.noise_id=P['training_noise_base']+self.pair*1000000+self.slot*10000+self.index
            self.noise=np.random.default_rng(self.noise_id).normal(0,[.03,math.radians(.17),.01,.1],(self.horizon+1,4))
            self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self._sense()
            info['noise_id']=self.noise_id
        return self.obs.copy(),info
