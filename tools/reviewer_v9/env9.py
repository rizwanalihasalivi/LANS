import boot9
import json
import math
import sys
sys.path.insert(0,str(boot9.ROOT/'tools/reviewer_v5'))
from history5 import HistoryEnv
from features9 import QueryController,make_observation,NEW
import numpy as np
P=json.loads((boot9.HERE/'protocol.json').read_text())
VALUES={'nominal':(.9,1.,.01),'tire':(.9,.7,.01),'delay20':(.9,1.,.02),'delay40':(.9,1.,.04),'delay100':(.9,1.,.1)}

class Env(HistoryEnv):
    def __init__(self,pair=0,slot=0,seed=6701,source='causal_history',case=None,scenario=None,mask_history=False):
        self.override_scenario=scenario;self.mask_history=mask_history
        self.raw=np.zeros(20,np.float32);self.query_meta=None
        super().__init__(pair,slot,seed,source=source,case=case,history=True)
    def reset(self,**kwargs):
        super().reset(**kwargs)
        scenario=self.override_scenario if self.fixed_case else str(self.np_random.choice(list(VALUES)))
        self.scenario=scenario;self.mu,self.stiffness,self.service=VALUES[scenario]
        if not self.fixed_case:
            self.noise_id=P['training_noise_base']+self.pair*1000000+self.slot*10000+self.index
            self.noise=np.random.default_rng(self.noise_id).normal(0,[.03,math.radians(.17),.01,.1],(self.horizon+1,4))
        comp=self.source.endswith('_comp') or self.source in P['arms']
        self.ctrl=QueryController(compensated=comp,baseline=self.source=='lqr')
        self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self._sense()
        return self.obs.copy(),{'noise_id':self.noise_id}
    def _sense(self):
        super()._sense()
        if not isinstance(self.ctrl,QueryController):return
        if self.ctrl.packet is not None:
            seq,t,_=self.ctrl.packet;self.ctrl.compensator.observe(int(seq),max(0.,self.tick*.01-t))
        self.raw=make_observation(self.state,self.estimate,self.measured_speed,self.ctrl.previews,self.ctrl,self.tick*.01)
        self.obs,self.query_meta=self.ctrl.prepare_query(self.raw,self.estimate,self.state[5],self.measured_speed,self.ctrl.previews,self.gain)
        if self.mask_history:self.obs[list(NEW)]=0.
