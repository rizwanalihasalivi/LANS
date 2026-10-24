"""Explicit small corrected-root training; never overwrites historical models."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.residual_path_env import ResidualPathEnv
from controllers.policy_bundle import save_bundle


def set_learning_rate(model, value):
    """Update SB3's effective schedule and existing optimizer, not just metadata."""
    if value<=0:
        raise ValueError('learning rate must be positive')
    model.learning_rate=float(value)
    model.lr_schedule=lambda _:float(value)
    for group in model.policy.optimizer.param_groups:
        group['lr']=float(value)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=1000);p.add_argument('--seed',type=int,default=101)
    p.add_argument('--speed',type=float,default=25.);a=p.parse_args()
    if a.output.exists():
        p.error('output must be a new directory')
    if a.steps<=0 or a.steps%100:
        p.error('steps must be a positive multiple of 100')
    env=VecNormalize(DummyVecEnv([lambda:ResidualPathEnv(vx=a.speed)]),norm_obs=True,norm_reward=True)
    model=PPO('MlpPolicy',env,seed=a.seed,n_steps=100,batch_size=50,learning_rate=3e-4,
              policy_kwargs={'net_arch':[64,64]},device='cpu',verbose=0)
    model.learn(a.steps);save_bundle(a.output,model,env);env.close()

if __name__=='__main__':
    main()
