"""Matched-budget standalone full-command and original-role residual PPO."""
import argparse, hashlib, json, os, time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from core import PROTOCOL
from environment import TrainingEnv

class Progress(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.start=time.time();self.last=0
    def _on_step(self):
        if self.num_timesteps-self.last>=10000:
            self.last=self.num_timesteps
            (self.out/'progress.json').write_text(json.dumps({'steps':self.num_timesteps,'wall_s':time.time()-self.start}))
        return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--role',choices=['full','residual'],required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    protocol=Path(__file__).with_name('protocol.json')
    (out/'protocol.json').write_bytes(protocol.read_bytes())
    start=time.time()
    env=DummyVecEnv([lambda i=i:Monitor(TrainingEnv(args.role,args.seed*100+i),str(out/f'episodes-{i}.csv')) for i in range(8)])
    env=VecNormalize(env,norm_obs=False,norm_reward=True,clip_reward=10.)
    model=PPO('MlpPolicy',env,n_steps=125,batch_size=200,n_epochs=10,learning_rate=.0003,gamma=.99,gae_lambda=.95,
              seed=args.seed,device='cpu',policy_kwargs={'net_arch':[64,64]},verbose=0)
    model.learn(total_timesteps=PROTOCOL['training_steps_per_seed_per_policy'],callback=Progress(out))
    assert model.num_timesteps==1000000
    model.save(str(out/'policy'));env.save(str(out/'normalization.pkl'))
    metadata={'seed':args.seed,'role':args.role,'steps':model.num_timesteps,'wall_s':time.time()-start,
              'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
              'source_sha256':{f:hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in ['core.py','environment.py','train.py']},
              'policy_sha256':hashlib.sha256((out/'policy.zip').read_bytes()).hexdigest()}
    (out/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n');env.close()
    print(json.dumps(metadata),flush=True)
if __name__=='__main__':main()
