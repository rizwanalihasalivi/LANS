import boot5
import hashlib
import json
import math
import numpy as np
import torch
from torch import nn
from aligned import AlignedEnv
from interface4 import FreshController
from supervisor import observation
from causal_student import load_causal

P=json.loads((boot5.HERE/'protocol.json').read_text());PROFILE='causal_filter_history_v5'


class Bridge(nn.Module):
    def __init__(self,kind,pair):
        super().__init__();seed=(701,802,903)[pair]
        folder=boot5.ROOT/(f'docs/research/causal-interface-2026-10-26/models/{seed}' if kind=='student' else f'docs/research/reviewer-aligned-v3/export/{seed}')
        if kind!='student':
            origin=json.loads((folder/'complete.json').read_text())
            checkpoint=boot5.ROOT/f'docs/research/reviewer-aligned-v3/training-{pair}/policy.zip'
            assert origin['source_ppo_sha256']==hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.base=load_causal(folder)
        # Old channel14 was identically0. The new causal feature is normalized
        # filter history, not the old unknown pending proposal. Exact old logits
        # are preserved at initialization by zeroing this unused input column.
        with torch.no_grad():self.base.mean[14]=0.;self.base.std[14]=1.;self.base.net[0].weight[:,14]=0.
    @property
    def mean(self):return self.base.mean
    @property
    def std(self):return self.base.std
    @property
    def net(self):return self.base.net
    def forward(self,x):return self.base(x)
    def predict(self,obs,deterministic=True):
        x=np.asarray(obs,np.float32)
        if x.shape!=(20,) or not np.isfinite(x).all() or np.any(x[[15,16,17,19]]):raise ValueError('v5 causal history features required')
        with torch.no_grad():index=int(self(torch.from_numpy(x)[None]).argmax(1).item())
        return index,None


class HistoryEnv(AlignedEnv):
    def __init__(self,pair=0,slot=0,seed=4701,history=True,case=None,source='ppo'):
        self.expose_history=history;self.source=source
        super().__init__(pair,slot,seed,case=case,baseline=source=='lqr')
    def _history(self):
        self.obs[14]=float(np.clip(getattr(self.ctrl,'filtered',0.)/.08,-1.,1.)) if self.expose_history else 0.
    def reset(self,**kwargs):
        super().reset(**kwargs)
        if not self.fixed_case:
            self.noise_id=P['training_noise_base']+self.pair*1000000+self.slot*10000+self.index
            self.noise=np.random.default_rng(self.noise_id).normal(0,[.03,math.radians(.17),.01,.1],(self.horizon+1,4))
            self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self._sense()
        self.service=max(.01,self.service)
        if not self.baseline_only:self.ctrl=FreshController()
        self.ctrl.previews=self.obs[6:9].astype(float)*.02
        self.obs=observation(self.state,self.estimate,self.measured_speed,self.ctrl.previews,self.ctrl,self.tick*.01)
        self._history();return self.obs.copy(),{'noise_id':self.noise_id}
    def _sense(self):super()._sense();self._history()
