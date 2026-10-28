import boot9
import argparse
import json
import sys
import time
sys.path.insert(0,str(boot9.ROOT/'tools/reviewer_v6'))
from credit6 import CreditPPO,CreditBuffer
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from policy9 import ObservedStandardizer,copy_actor
from model9 import Bridge
from env9 import Env,P
from features9 import NEW
import torch
from torch import nn
import numpy as np

class Progress(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.seen=0;self.submitted=0;self.active=0
    def _on_step(self):
        mask=np.array([i['submitted'] for i in self.locals['infos']],np.float32);self.model.rollout_buffer.next_credit=mask
        self.seen+=len(mask);self.submitted+=int(mask.sum());self.active+=sum(abs(i['command']-i['baseline'])>1e-10 for i in self.locals['infos'])
        if self.seen%10000==0:
            x=dict(steps=self.seen,submitted=self.submitted,active=self.active);(self.out/'progress.json').write_text(json.dumps(x)+'\n');print(x,flush=True)
        return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,choices=range(3),required=True);p.add_argument('--arm',choices=P['arms'],required=True);p.add_argument('--output',type=boot9.Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);seed=P['seeds'][a.pair];initial=Bridge('ppo',a.pair);cfg=P['ppo']
    env=VecNormalize(DummyVecEnv([lambda slot=slot:Env(a.pair,slot,seed+slot,source=a.arm,mask_history=a.arm=='legacy_history') for slot in range(4)]),norm_obs=False,norm_reward=True,clip_reward=10.)
    model=CreditPPO('MlpPolicy',env,seed=seed,device='cpu',policy_kwargs=dict(net_arch=dict(pi=[64,64],vf=[64,64]),activation_fn=nn.Tanh,features_extractor_class=ObservedStandardizer,features_extractor_kwargs=dict(mean=initial.mean.numpy(),std=initial.std.numpy())),**{k:v for k,v in cfg.items() if k!='n_envs'})
    copy_actor(model,initial)
    with torch.no_grad():model.policy.mlp_extractor.value_net[0].weight[:,list(NEW)]=0.
    model.rollout_buffer=CreditBuffer(model.n_steps,model.observation_space,model.action_space,device='cpu',gamma=model.gamma,gae_lambda=model.gae_lambda,n_envs=4)
    model.set_logger(configure(str(out),['csv']));model.save(out/'initial.zip');cb=Progress(out);start=time.perf_counter();model.learn(total_timesteps=P['steps_each'],callback=cb)
    model.save(out/'policy.zip');env.save(out/'reward-normalization.pkl');assert model.num_timesteps==cb.seen==P['steps_each']
    if a.arm=='legacy_history':assert torch.count_nonzero(model.policy.mlp_extractor.policy_net[0].weight[:,list(NEW)])==0
    meta=dict(pair=a.pair,arm=a.arm,steps=cb.seen,submitted=cb.submitted,actor_credit_samples=cb.submitted,active=cb.active,endpoint_eligible=True,new_history_column_norm=float(model.policy.mlp_extractor.policy_net[0].weight[:,list(NEW)].norm()),wall_seconds=time.perf_counter()-start)
    (out/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');env.close()

if __name__=='__main__':main()
