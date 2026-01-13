"""
Transfer learning script: load pretrained PPO policy, freeze feature extractor, fine-tune on target env.
Usage: python transfer_train.py --pretrained ppo_lqr_base --save ppo_lqr_transfer --vx_target 20.0
"""
import argparse
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.lqr_env import LQREnv


def make_env_fn(vx=15.0):
    def _init():
        return LQREnv(dt=0.01, vx=vx)
    return _init


def freeze_feature_extractor(model):
    # For SB3 MlpPolicy, the feature extractor is mlp_extractor
    for name, param in model.policy.named_parameters():
        if 'mlp_extractor' in name:
            param.requires_grad = False


def unfreeze_all(model):
    for param in model.policy.parameters():
        param.requires_grad = True


def transfer(pretrained_path='ppo_lqr_base', save_path='ppo_lqr_transfer', vx_target=20.0):
    env = DummyVecEnv([make_env_fn(vx_target)])
    env = VecNormalize(env, norm_obs=True, norm_reward=False)

    model = PPO.load(pretrained_path, env=env)
    freeze_feature_extractor(model)

    # reduce lr for fine-tuning
    model.learning_rate = 1e-5
    model.learn(total_timesteps=int(2e5), reset_num_timesteps=False)

    # progressive unfreeze: unfreeze all and train a bit more
    unfreeze_all(model)
    model.learning_rate = 1e-6
    model.learn(total_timesteps=int(1e5), reset_num_timesteps=False)

    model.save(save_path)
    env.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--pretrained', type=str, default='ppo_lqr_base')
    p.add_argument('--save', type=str, default='ppo_lqr_transfer')
    p.add_argument('--vx_target', type=float, default=20.0)
    args = p.parse_args()
    transfer(pretrained_path=args.pretrained, save_path=args.save, vx_target=args.vx_target)
