import boot5
import argparse
import json
import time
import torch
from torch import nn
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from policy9 import ObservedStandardizer,copy_actor
from history5 import HistoryEnv,Bridge,P,PROFILE


class Progress(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.seen=0;self.active=0;self.history=0;self.futile=False
    def _on_step(self):
        for row in self.locals['infos']:
            self.seen+=1;self.active+=abs(row['command']-row['baseline'])>1e-10;self.history+=abs(row['obs14'])>1e-8
        if self.seen%1000==0:
            record=dict(steps=self.seen,active=self.active,nonzero_history=self.history);(self.out/'progress.json').write_text(json.dumps(record)+'\n');print(record,flush=True)
        if self.seen==10000:
            self.model.save(self.out/'checkpoint10000.zip')
            if self.active/self.seen<=.001:self.futile=True;return False
        return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,choices=range(3),required=True);p.add_argument('--arm',choices=P['arms'],required=True);p.add_argument('--output',type=boot5.Path,required=True)
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1);torch.set_num_interop_threads(1)
    seed=P['seeds'][args.pair];bridge=Bridge('ppo',args.pair);cfg=P['ppo']
    env=VecNormalize(DummyVecEnv([lambda slot=slot:HistoryEnv(args.pair,slot,seed+slot,history=args.arm=='history') for slot in range(4)]),norm_obs=False,norm_reward=True,clip_reward=10.)
    model=PPO('MlpPolicy',env,seed=seed,device='cpu',policy_kwargs=dict(net_arch=dict(pi=[64,64],vf=[64,64]),activation_fn=nn.Tanh,
        features_extractor_class=ObservedStandardizer,features_extractor_kwargs=dict(mean=bridge.mean.numpy(),std=bridge.std.numpy())),**{k:v for k,v in cfg.items() if k!='n_envs'})
    copy_actor(model,bridge)
    with torch.no_grad():model.policy.mlp_extractor.value_net[0].weight[:,14]=0.
    assert torch.count_nonzero(model.policy.mlp_extractor.policy_net[0].weight[:,14])==0
    model.set_logger(configure(str(out),['csv']));model.save(out/'initial.zip');callback=Progress(out);start=time.perf_counter()
    model.learn(total_timesteps=100000,callback=callback);model.save(out/'policy.zip');env.save(out/'reward-normalization.pkl')
    assert model.num_timesteps==callback.seen
    if args.arm=='nohistory':assert torch.count_nonzero(model.policy.mlp_extractor.policy_net[0].weight[:,14])==0
    metadata=dict(arm=args.arm,pair=args.pair,seed=seed,steps=model.num_timesteps,futile=callback.futile,endpoint_eligible=model.num_timesteps==100000 and not callback.futile,
        profile=PROFILE,history_column_norm=float(model.policy.mlp_extractor.policy_net[0].weight[:,14].norm()),wall_seconds=time.perf_counter()-start,protocol=P)
    (out/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n');env.close()


if __name__=='__main__':main()
