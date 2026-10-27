import boot3
import argparse
import json
import time
import numpy as np
import torch
from torch import nn
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from causal_student import load_causal
from policy9 import ObservedStandardizer,copy_actor
from aligned import AlignedEnv,P


class Progress(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.active=0;self.seen=0;self.futile=False
    def _on_step(self):
        for row in self.locals['infos']:
            self.active+=abs(row['command']-row['baseline'])>1e-10;self.seen+=1
        if self.seen%1000==0:
            result=dict(steps=self.seen,nonzero_correction_transitions=self.active)
            (self.out/'progress.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
        if self.seen==10000:
            self.model.save(self.out/'checkpoint10000.zip')
            if self.active/self.seen<=.001:self.futile=True;return False
        return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,required=True,choices=range(3));p.add_argument('--output',type=boot3.Path,required=True)
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);cfg=P['training'];seed=cfg['seeds'][args.pair]
    student=load_causal(boot3.ROOT/f'docs/research/causal-interface-2026-10-26/models/{cfg["student_seeds"][args.pair]}')
    env=VecNormalize(DummyVecEnv([lambda slot=slot:AlignedEnv(args.pair,slot,seed+slot) for slot in range(4)]),norm_obs=False,norm_reward=True,clip_reward=10.)
    kwargs={k:cfg[k] for k in ('n_steps','batch_size','n_epochs','learning_rate','clip_range','target_kl','gamma','gae_lambda','ent_coef','vf_coef')}
    model=PPO('MlpPolicy',env,seed=seed,device='cpu',policy_kwargs=dict(net_arch=dict(pi=[64,64],vf=[64,64]),activation_fn=nn.Tanh,
        features_extractor_class=ObservedStandardizer,features_extractor_kwargs=dict(mean=student.mean.numpy(),std=student.std.numpy())),**kwargs)
    copy_actor(model,student);model.set_logger(configure(str(out),['csv']));model.save(out/'initial.zip')
    callback=Progress(out);start=time.perf_counter();model.learn(total_timesteps=100000,callback=callback);model.save(out/'policy.zip');env.save(out/'reward-normalization.pkl')
    assert model.num_timesteps==callback.seen
    (out/'complete.json').write_text(json.dumps(dict(pair=args.pair,seed=seed,steps=model.num_timesteps,futile=callback.futile,
        final_endpoint_eligible=model.num_timesteps==100000 and not callback.futile,wall_seconds=time.perf_counter()-start,protocol=P),indent=2)+'\n')
    env.close()


if __name__=='__main__':main()
