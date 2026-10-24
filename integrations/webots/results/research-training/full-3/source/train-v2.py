"""Matched-budget PPO with bounded positive survival reward and constrained exploration."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from comparison import configure_lqr
from train import Progress

source=Path(__file__).with_name('environment-v2.py')
spec=importlib.util.spec_from_file_location('environment_v2',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--role',choices=['full','residual'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--steps',type=int,default=1000000);args=p.parse_args()
    if args.steps%1000:raise ValueError('steps must be multiple of 1000')
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    out=args.output;out.mkdir(parents=True,exist_ok=False);(out/'source').mkdir()
    files=['core.py','environment.py','environment-v2.py','train.py','train-v2.py','comparison.py','protocol.json','comparison-protocol.json','final-training-protocol.json']
    hashes={}
    for name in files:
        data=Path(__file__).with_name(name).read_bytes();(out/'source'/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    start=time.time()
    env=DummyVecEnv([lambda i=i:Monitor(module.SurvivalEnv(args.role,args.seed*100+i),str(out/f'episodes-{i}.csv')) for i in range(8)])
    env=VecNormalize(env,norm_obs=False,norm_reward=True,clip_reward=10.)
    model=PPO('MlpPolicy',env,n_steps=125,batch_size=200,n_epochs=10,learning_rate=.0003,gamma=.99,gae_lambda=.95,
              seed=args.seed,device='cpu',policy_kwargs={'net_arch':[64,64],'log_std_init':-2.},verbose=0)
    model.learn(total_timesteps=args.steps,callback=Progress(out));assert model.num_timesteps==args.steps
    model.save(str(out/'policy'));env.save(str(out/'normalization.pkl'))
    metadata={'seed':args.seed,'role':args.role,'steps':model.num_timesteps,'wall_s':time.time()-start,'training_profile':'positive_survival_v2',
              'final_training_protocol_sha256':hashes['final-training-protocol.json'],'protocol_sha256':hashes['protocol.json'],'comparison_protocol_sha256':hashes['comparison-protocol.json','final-training-protocol.json'],'source_sha256':hashes,
              'policy_sha256':hashlib.sha256((out/'policy.zip').read_bytes()).hexdigest()}
    (out/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n');env.close();print(json.dumps(metadata),flush=True)
if __name__=='__main__':main()
