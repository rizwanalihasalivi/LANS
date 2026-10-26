"""Six frozen 25k causal PPO pilots; matched extra budget, exact actor transfer."""
import common
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.logger import configure
from supervisor import P
from environment import CausalEnv
from policy9 import ObservedStandardizer, copy_actor
from causal_student import load_causal


def student_folder(pair):
    return common.ROOT / 'docs/research/causal-interface-2026-10-26/models' / str(P['student_seeds'][pair])


class Progress(BaseCallback):
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.transitions = 0
        self.accepted = 0
        self.failures = 0

    def _on_step(self):
        for info in self.locals['infos']:
            self.transitions += 1
            self.accepted += info['weight'] > 0
            self.failures += info['failed']
        if self.transitions % 1000 == 0:
            row = dict(steps=self.transitions, accepted=self.accepted, failures=self.failures)
            (self.folder/'progress.json').write_text(json.dumps(row, indent=2)+'\n')
            print(json.dumps(row), flush=True)
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pair', type=int, choices=range(3), required=True)
    p.add_argument('--arm', choices=P['arms'], required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    seed = P['seeds'][args.pair]
    student = load_causal(student_folder(args.pair))
    cfg = P['ppo']
    env = VecNormalize(DummyVecEnv([
        lambda slot=slot: CausalEnv(args.pair, slot, seed+slot)
        for slot in range(cfg['n_envs'])]), norm_obs=False, norm_reward=True, clip_reward=10.)
    model = PPO('MlpPolicy', env, device='cpu', seed=seed, verbose=0,
        policy_kwargs=dict(net_arch=dict(pi=[64,64], vf=[64,64]), activation_fn=nn.Tanh,
            features_extractor_class=ObservedStandardizer,
            features_extractor_kwargs=dict(mean=student.mean.numpy(), std=student.std.numpy())),
        **{k:v for k,v in cfg.items() if k != 'n_envs'})
    if args.arm == 'finetune':
        copy_actor(model, student)
        # Exact transfer and causal-query compatibility before any optimization.
        check = np.zeros(20, dtype=np.float32)
        a, _ = student.predict(check)
        b, _ = model.predict(check, deterministic=True)
        assert abs(float(a[0])*.08-P['candidates_rad'][int(b)]) < 1e-8
    model.set_logger(configure(str(args.output), ['csv']))
    model.save(args.output/'initial.zip')
    initial_parameters = {k:v.detach().clone() for k,v in model.policy.state_dict().items()}
    callback = Progress(args.output)
    start = time.perf_counter()
    model.learn(total_timesteps=P['steps_each'], callback=callback)
    assert model.num_timesteps == callback.transitions == P['steps_each']
    assert any(not torch.equal(initial_parameters[k], v) for k,v in model.policy.state_dict().items())
    model.save(args.output/'policy.zip')
    env.save(args.output/'reward-normalization.pkl')
    meta = dict(arm=args.arm, pair=args.pair, seed=seed, steps=model.num_timesteps,
                wall_s=time.perf_counter()-start, protocol=P, profile='causal_residual_campaign_v1',
                student_hash=hashlib.sha256((student_folder(args.pair)/'student.pt').read_bytes()).hexdigest(),
                normalization='frozen causal TRAIN; same paired scratch/finetune',
                original_student_pretraining_is_extra=True)
    (args.output/'complete.json').write_text(json.dumps(meta, indent=2)+'\n')
    env.close()


if __name__ == '__main__':
    main()
