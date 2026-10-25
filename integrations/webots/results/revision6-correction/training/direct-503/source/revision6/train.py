"""Fixed100k checkpoints, no selection; saves PPO optimization/execution diagnostics."""
import argparse,csv,json,subprocess,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from bootstrap import HERE,RESEARCH
from environment import PilotEnv


class Diagnostics(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.rows=[];self.active=0;self.count=0;self.sums={}
    def _on_step(self):
        for info in self.locals['infos']:
            self.count+=1;self.active+=info['gate_weight']>0
            for k in ('reward_tracking','reward_effort','reward_change','reward_survival','reward_relative'):
                self.sums[k]=self.sums.get(k,0.)+info[k]
        return True
    def _on_rollout_end(self):
        b=self.model.rollout_buffer
        self.rows.append(dict(steps=self.num_timesteps,active_fraction=self.active/self.count,
            advantage_mean=float(b.advantages.mean()),advantage_std=float(b.advantages.std()),
            return_mean=float(b.returns.mean()),physical_std_rad=float(.08*self.model.policy.log_std.exp().detach().cpu().mean()),
            **{k:v/self.count for k,v in self.sums.items()}))
        (self.out/'progress.json').write_text(json.dumps(self.rows[-1],indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['direct','execution'],required=True)
    p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    protocol=json.loads((HERE/'protocol.json').read_text());assert a.seed in protocol['seeds']
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    a.output.mkdir(parents=True,exist_ok=False)
    sources=list(HERE.glob('*.py'))+[HERE/'protocol.json',RESEARCH/'revision5/execution.py',RESEARCH/'revision5/execution_env.py',
        RESEARCH/'revision2/gating.py',RESEARCH/'revision2/plant.py',RESEARCH/'core.py',RESEARCH/'comparison.py',
        RESEARCH/'comparison-protocol.json',RESEARCH/'revision4/reward_model.py']
    for path in sources:
        target=a.output/'source'/path.relative_to(RESEARCH);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
    start=time.perf_counter()
    env=VecNormalize(DummyVecEnv([lambda i=i:Monitor(PilotEnv(a.arm,a.seed+i),str(a.output/f'episodes-{i}.csv')) for i in range(8)]),
        norm_obs=False,norm_reward=True,clip_reward=10.)
    model=PPO('MlpPolicy',env,n_steps=125,batch_size=200,n_epochs=10,learning_rate=.0003,gamma=.99,gae_lambda=.95,
        seed=a.seed,device='cpu',policy_kwargs={'net_arch':[64,64],'log_std_init':-2.},verbose=0)
    model.set_logger(configure(str(a.output),['csv']));callback=Diagnostics(a.output)
    model.learn(total_timesteps=protocol['steps_per_arm_seed'],callback=callback)
    assert model.num_timesteps==100000
    model.logger.dump(model.num_timesteps);model.save(a.output/'policy.zip');env.save(a.output/'normalization.pkl');env.close()
    with (a.output/'diagnostics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=callback.rows[0],lineterminator='\n');w.writeheader();w.writerows(callback.rows)
    meta=dict(arm=a.arm,seed=a.seed,steps=model.num_timesteps,observation_dimensions=20,residual_scale_rad=.08,
        profile='correction_quality_v6',wall_s=time.perf_counter()-start,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),
        normalization='reward-only; fixed-scaled actor observations',protocol=protocol)
    (a.output/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({k:meta[k] for k in ('arm','seed','steps','wall_s')}),flush=True)


if __name__=='__main__':main()
