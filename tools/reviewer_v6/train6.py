import boot6
import argparse
import json
import math
import time
import numpy as np
import torch
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from history5 import HistoryEnv
from credit6 import CreditPPO,CreditBuffer,TRAIN_SOURCE

P=json.loads((boot6.HERE/'protocol.json').read_text())

class CreditEnv(HistoryEnv):
    def reset(self,**kwargs):
        super().reset(**kwargs)
        if not self.fixed_case:
            self.noise_id=P['training_noise_base']+self.pair*1000000+self.slot*10000+self.index
            self.noise=np.random.default_rng(self.noise_id).normal(0,[.03,math.radians(.17),.01,.1],(self.horizon+1,4))
            self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self._sense()
        return self.obs.copy(),{'noise_id':self.noise_id}

class CreditCallback(BaseCallback):
    def __init__(self,arm,out):super().__init__();self.arm=arm;self.out=out;self.submitted=0;self.seen=0;self.active=0
    def _on_step(self):
        masks=np.array([r['submitted'] for r in self.locals['infos']],np.float32)
        self.model.rollout_buffer.next_credit=masks if self.arm=='submitted_only' else np.ones_like(masks)
        self.seen+=len(masks);self.submitted+=int(masks.sum());self.active+=sum(abs(r['command']-r['baseline'])>1e-10 for r in self.locals['infos'])
        if self.seen%10000==0:
            row=dict(steps=self.seen,submitted=self.submitted,active=self.active)
            (self.out/'progress.json').write_text(json.dumps(row)+'\n');print(row,flush=True)
        return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,choices=range(3),required=True);p.add_argument('--arm',choices=P['arms'],required=True);p.add_argument('--output',type=boot6.Path,required=True);a=p.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1);torch.set_num_interop_threads(1)
    seed=P['seeds'][a.pair]
    env=VecNormalize(DummyVecEnv([lambda slot=slot:CreditEnv(a.pair,slot,seed+slot,history=False) for slot in range(4)]),norm_obs=False,norm_reward=True,clip_reward=10.)
    model=CreditPPO.load(boot6.ROOT/f'docs/research/reviewer-history-v5/nohistory-{a.pair}/policy.zip',env=env,device='cpu')
    model.set_random_seed(seed)
    model.rollout_buffer=CreditBuffer(model.n_steps,model.observation_space,model.action_space,device='cpu',gamma=model.gamma,gae_lambda=model.gae_lambda,n_envs=4)
    model.set_logger(configure(str(out),['csv']));model.save(out/'initial.zip');cb=CreditCallback(a.arm,out);start=time.perf_counter()
    model.learn(total_timesteps=P['steps_each'],callback=cb);model.save(out/'policy.zip');env.save(out/'reward-normalization.pkl')
    assert model.num_timesteps==cb.seen==P['steps_each']
    assert torch.count_nonzero(model.policy.mlp_extractor.policy_net[0].weight[:,14])==0
    result=dict(arm=a.arm,pair=a.pair,seed=seed,steps=cb.seen,submitted=cb.submitted,discarded=cb.seen-cb.submitted,
        actor_credit_samples=cb.submitted if a.arm=='submitted_only' else cb.seen,active=cb.active,endpoint_eligible=True,
        history_column_norm=0.,profile='causal_filter_history_v5',wall_seconds=time.perf_counter()-start)
    (out/'complete.json').write_text(json.dumps(result,indent=2)+'\n');env.close()

if __name__=='__main__':main()
