"""Replay an actual 10k-step checkpoint interval without changing study endpoints."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/reviewer_v12'))
import boot12
import json
import pickle
import random
import tempfile
import numpy as np
import torch
from stable_baselines3.common.logger import configure
from checkpoint12 import load, atomic_json, digest
from train12 import Credit


def same(a, b):
    if isinstance(a, torch.Tensor): torch.testing.assert_close(a, b, rtol=0, atol=0)
    elif isinstance(a, np.ndarray): np.testing.assert_array_equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a: same(a[key], b[key])
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b): same(x, y)
    else: assert a == b, (a, b)


def restore_at(checkpoints, name, signature):
    # load() follows an authenticated pointer; create an isolated view without
    # touching the real study's current latest pointer.
    with tempfile.TemporaryDirectory() as d:
        temp = Path(d)
        (temp/name).symlink_to((checkpoints/name).resolve(), target_is_directory=True)
        atomic_json(temp/'latest.json', dict(folder=name, manifest_sha256=digest(checkpoints/name/'manifest.json')))
        return load(temp, signature)


def main():
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    run = ROOT/'docs/research/ppo-audit-v12'
    signature = digest(run/'manifest.json')
    checkpoints = run/'continued-0/checkpoints'
    start, end = 'step-000010000', 'step-000020000'
    model, env, _ = restore_at(checkpoints, start, signature)
    model.set_logger(configure(None, []))
    _, callback = model._setup_learn(50000-model.num_timesteps, Credit(), reset_num_timesteps=False)
    while model.num_timesteps < 20000:
        assert model.collect_rollouts(env, callback, model.rollout_buffer, model.n_steps)
        model._update_current_progress_remaining(model.num_timesteps, 50000)
        model.train()
    python_rng, numpy_rng, torch_rng = random.getstate(), np.random.get_state(), torch.get_rng_state()
    expected, other, _ = restore_at(checkpoints, end, signature)
    same(model.policy.state_dict(), expected.policy.state_dict())
    same(model.policy.optimizer.state_dict(), expected.policy.optimizer.state_dict())
    same(model._last_obs, expected._last_obs); same(model._last_episode_starts, expected._last_episode_starts)
    same(model.audit_counts, expected.audit_counts); same(model._n_updates, expected._n_updates)
    same(env.ret_rms.__dict__, other.ret_rms.__dict__); same(env.returns, other.returns)
    same(env.venv._seeds, other.venv._seeds)
    for a, b in zip(env.venv.envs, other.venv.envs):
        for key in ('state', 'estimate', 'cov', 'previous', 'noise', 'obs', 'raw', 'tick', 'index', 'noise_id'):
            same(getattr(a, key), getattr(b, key))
        same(a.np_random.bit_generator.state, b.np_random.bit_generator.state)
        for key in ('packet', 'pending', 'sequence', 'last_sequence', 'weight', 'good', 'filtered', 'last_qualified_sequence', 'last_qualified_time'):
            same(getattr(a.ctrl, key), getattr(b.ctrl, key))
        same(a.ctrl.compensator.__dict__, b.ctrl.compensator.__dict__)
    same(python_rng, random.getstate()); same(numpy_rng, np.random.get_state()); same(torch_rng, torch.get_rng_state())
    result = dict(source_sha256=digest(Path(__file__)), interval=[10000, 20000], replayed_environment_steps=10000,
                  source_checkpoint_sha256=digest(checkpoints/start/'manifest.json'),
                  expected_checkpoint_sha256=digest(checkpoints/end/'manifest.json'),
                  exact_model_optimizer_environment_queue_normalizer_rng_match=True,
                  scope='Separate-process replay of an actual continued-0 training interval. No new endpoint or selected evidence is created.')
    atomic_json(run/'resume-replay.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
