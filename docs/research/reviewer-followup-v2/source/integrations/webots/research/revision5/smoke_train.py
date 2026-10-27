"""1000-step interface smoke, not a policy performance experiment."""
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from bootstrap import HERE
from execution_env import ExecutionEnv


class Diagnostics(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.rows=[];self.rollouts=[]
    def _on_step(self):
        for info in self.locals['infos']:
            self.rows.append({k:v for k,v in info.items() if k not in ('terminal_observation','TimeLimit.truncated')})
        return True
    def _on_rollout_end(self):
        b=self.model.rollout_buffer
        self.rollouts.append(dict(steps=self.num_timesteps,advantage_mean=float(np.mean(b.advantages)),
            advantage_std=float(np.std(b.advantages)),return_mean=float(np.mean(b.returns))))
    def save(self):
        for name,rows in [('transitions',self.rows),('rollouts',self.rollouts)]:
            with (self.out/(name+'.csv')).open('w') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--randomize',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    env=VecNormalize(DummyVecEnv([lambda:ExecutionEnv(seed=909,randomize=a.randomize)]),norm_obs=False,norm_reward=True)
    model=PPO('MlpPolicy',env,seed=909,n_steps=100,batch_size=50,n_epochs=10,learning_rate=3e-4,
              policy_kwargs={'net_arch':[64,64],'log_std_init':-2.},device='cpu')
    model.set_logger(configure(str(a.output),['csv']));callback=Diagnostics(a.output)
    model.learn(1000,callback=callback);model.logger.dump(model.num_timesteps);callback.save()
    model.save(a.output/'policy.zip');env.save(a.output/'normalization.pkl')
    metadata=dict(purpose='interface smoke only',steps=model.num_timesteps,observation_dimensions=20,
        residual_scale_rad=.08,initial_physical_std_rad=.08*np.exp(-2),randomize=a.randomize,
        sources={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in HERE.glob('*.py')})
    (a.output/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n')
    env.close()

if __name__=='__main__':main()
