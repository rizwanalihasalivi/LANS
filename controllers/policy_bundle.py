"""Explicit corrected-root policy contract. Legacy archives are incompatible."""
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_bundle(folder, model, normalized_env):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    model.save(folder/'policy.zip'); normalized_env.save(folder/'normalization.pkl')
    manifest = dict(contract='world-bicycle-residual-v2', role='residual', action_scale_rad=.08,
                    observation='error4-speed-preview4-latency2-v2', observations=11,
                    files={n:digest(folder/n) for n in ('policy.zip','normalization.pkl')})
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


class PolicyBundle:
    def __init__(self, folder):
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
        from envs.residual_path_env import ResidualPathEnv
        folder=Path(folder); m=json.loads((folder/'manifest.json').read_text())
        if (m['contract'],m['role'],m['action_scale_rad'],m['observation'],m['observations']) != (
            'world-bicycle-residual-v2','residual',.08,'error4-speed-preview4-latency2-v2',11):
            raise ValueError('incompatible policy contract; legacy policies require retraining')
        for name in ('policy.zip','normalization.pkl'):
            if digest(folder/name)!=m['files'][name]:
                raise ValueError('bundle hash mismatch: '+name)
        self.normalizer=VecNormalize.load(folder/'normalization.pkl',DummyVecEnv([ResidualPathEnv]))
        self.normalizer.training=False; self.normalizer.norm_reward=False
        self.model=PPO.load(folder/'policy.zip',device='cpu')
        if self.model.observation_space.shape!=(11,) or self.model.action_space.shape!=(1,):
            raise ValueError('policy spaces disagree with manifest')

    def predict(self, observation, deterministic=True):
        obs=np.asarray(observation,dtype=np.float32)
        if obs.shape!=(11,) or not np.isfinite(obs).all():
            raise ValueError('finite 11-component observation required')
        return self.model.predict(self.normalizer.normalize_obs(obs), deterministic=deterministic)
