"""
PPO training script for LQREnv using Stable-Baselines3.
Usage: python ppo_train.py --timesteps 1000000 --save ppo_lqr_base
"""
import argparse
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from envs.lqr_env import LQREnv


def make_env_fn(vx=15.0):
    def _init():
        env = LQREnv(dt=0.01, vx=vx)
        return env
    return _init


def train(total_timesteps=1_000_000, save_path='ppo_lqr_base', vx=15.0, n_envs=4):
    env_fns = [make_env_fn(vx) for _ in range(n_envs)]
    env = DummyVecEnv(env_fns)
    env = VecNormalize(env, norm_obs=True, norm_reward=False)

    policy_kwargs = dict(net_arch=[dict(pi=[64, 64], vf=[64, 64])])

    model = PPO('MlpPolicy', env, verbose=1, policy_kwargs=policy_kwargs,
                learning_rate=3e-4, n_steps=256, batch_size=64, n_epochs=10, ent_coef=0.0)

    # callbacks
    checkpoint_callback = CheckpointCallback(save_freq=100_000, save_path='./checkpoints/', name_prefix='ppo_lqr')
    eval_env = DummyVecEnv([make_env_fn(vx)])
    eval_env = VecNormalize(eval_env, norm_obs=True, norm_reward=False)
    eval_callback = EvalCallback(eval_env, best_model_save_path='./best_model/', log_path='./logs/', eval_freq=50_000, deterministic=True, render=False)

    model.learn(total_timesteps=total_timesteps, callback=[checkpoint_callback, eval_callback])
    model.save(save_path)
    env.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--timesteps', type=int, default=1_000_000)
    p.add_argument('--save', type=str, default='ppo_lqr_base')
    p.add_argument('--vx', type=float, default=15.0)
    p.add_argument('--n_envs', type=int, default=4)
    args = p.parse_args()
    train(total_timesteps=args.timesteps, save_path=args.save, vx=args.vx, n_envs=args.n_envs)
