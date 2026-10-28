import boot11
import argparse
import hashlib
import json
import sys
import time
sys.path.insert(0,str(boot11.ROOT/'tools/reviewer_v6'))
from credit6 import CreditPPO,CreditBuffer
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from env11 import Env,P
import torch
import numpy as np


def initialize(pair):
    seed=P['training_seeds'][pair];old=boot11.ROOT/f'docs/research/reviewer-pipeline-v9/causal_history-{pair}'
    vec=DummyVecEnv([lambda slot=slot:Env(pair,slot,seed+slot,source='newppo_rk',mask_history=False) for slot in range(4)])
    env=VecNormalize.load(old/'reward-normalization.pkl',vec);env.training=True;env.norm_obs=False
    with (old/'policy.zip').open('rb') as file:model=CreditPPO.load(file,env=env,device='cpu',force_reset=True)
    prior_updates=model._n_updates
    model.seed=seed;model.set_random_seed(seed)
    model.rollout_buffer=CreditBuffer(model.n_steps,model.observation_space,model.action_space,device='cpu',gamma=model.gamma,gae_lambda=model.gae_lambda,n_envs=4)
    return model,env,old,prior_updates

class Progress(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.seen=self.submitted=self.active=0
    def _on_step(self):
        mask=np.array([i['submitted'] for i in self.locals['infos']],np.float32);self.model.rollout_buffer.next_credit=mask
        self.seen+=len(mask);self.submitted+=int(mask.sum());self.active+=sum(abs(i['command']-i['baseline'])>1e-10 for i in self.locals['infos'])
        if self.seen%10000==0:
            row=dict(new_steps=self.seen,submitted=self.submitted,active=self.active);(self.out/'progress.json').write_text(json.dumps(row)+'\n');print(row,flush=True)
        return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,choices=range(3),required=True);p.add_argument('--output',type=boot11.Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);model,env,old,prior_updates=initialize(a.pair)
    model.set_logger(configure(str(out),['csv']));model.save(out/'initial.zip');env.save(out/'initial-normalization.pkl')
    cb=Progress(out);start=time.perf_counter();model.learn(total_timesteps=P['steps_each'],callback=cb,reset_num_timesteps=True)
    assert model.num_timesteps==cb.seen==P['steps_each'];model.save(out/'policy.zip');env.save(out/'reward-normalization.pkl')
    meta=dict(pair=a.pair,seed=P['training_seeds'][a.pair],additional_steps=cb.seen,submitted=cb.submitted,active=cb.active,prior_updates=prior_updates,final_updates=model._n_updates,wall_seconds=time.perf_counter()-start,source_sha256={name:hashlib.sha256((old/name).read_bytes()).hexdigest() for name in ('policy.zip','reward-normalization.pkl')},endpoint_eligible=True)
    (out/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');env.close();print(json.dumps(meta),flush=True)
if __name__=='__main__':main()
