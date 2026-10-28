"""Atomic, checked PPO update-boundary snapshots, including environment and RNG.

Only locally produced, hash-verified trusted checkpoints are unpickled. A killed
in-flight update is replayed from the latest committed boundary, not skipped.
"""
import boot12
import hashlib
import json
import os
import pickle
import random
import uuid
import numpy as np
import torch
from credit6 import CreditPPO, CreditBuffer


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path, data):
    temp = path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    with temp.open('w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    sync_dir(path.parent)


def save(model, root, signature):
    """Call after train(), when the full rollout has already been consumed."""
    root.mkdir(parents=True, exist_ok=True)
    number = int(model.num_timesteps)
    name = f'step-{number:09d}'
    final = root/name
    if final.exists():
        meta = verify(final, signature)
        if meta['steps'] != number or meta['updates'] != model._n_updates:
            raise ValueError('Conflicting committed checkpoint')
        atomic_json(root/'latest.json', dict(folder=name, manifest_sha256=digest(final/'manifest.json')))
        return final
    partial = root/(name+'.partial-'+uuid.uuid4().hex)
    partial.mkdir()
    env = model.get_env()
    # VecNormalize.__getstate__ deliberately omits venv and returns.
    state = dict(normalizer=env, venv=env.venv, returns=env.returns.copy(),
                 python_rng=random.getstate(), numpy_rng=np.random.get_state(), torch_rng=torch.get_rng_state())
    with (partial/'state.pkl').open('wb') as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.flush(); os.fsync(f.fileno())
    with (partial/'model.zip').open('wb') as f:
        model.save(f)
        f.flush()
        os.fsync(f.fileno())
    meta = dict(signature=signature, steps=number, updates=model._n_updates,
                python_version=__import__('sys').version, numpy_version=np.__version__, torch_version=torch.__version__,
                sha256={p.name: digest(p) for p in partial.iterdir()})
    atomic_json(partial/'manifest.json', meta)
    sync_dir(partial)
    os.rename(partial, final)
    sync_dir(root)
    atomic_json(root/'latest.json', dict(folder=name, manifest_sha256=digest(final/'manifest.json')))
    return final


def verify(folder, signature):
    meta = json.loads((folder/'manifest.json').read_text())
    if meta['signature'] != signature:
        raise ValueError('Checkpoint source/protocol signature changed')
    for name, expected in meta['sha256'].items():
        if digest(folder/name) != expected:
            raise ValueError('Checkpoint checksum mismatch: '+name)
    if (meta['numpy_version'], meta['torch_version'], meta['python_version']) != (
            np.__version__, torch.__version__, __import__('sys').version):
        raise ValueError('Exact-resume Python/NumPy/Torch environment changed')
    return meta


def load(root, signature):
    pointer = json.loads((root/'latest.json').read_text())
    name = pointer['folder']
    if '/' in name or not name.startswith('step-') or '.partial' in name:
        raise ValueError('Invalid checkpoint pointer')
    folder = root/name
    if digest(folder/'manifest.json') != pointer['manifest_sha256']:
        raise ValueError('Checkpoint manifest checksum mismatch')
    meta = verify(folder, signature)
    with (folder/'state.pkl').open('rb') as f:
        state = pickle.load(f)
    env = state['normalizer']
    env.set_venv(state['venv'])
    env.returns = state['returns']
    with (folder/'model.zip').open('rb') as f:
        # Loading with env=env would reseed the restored vector environment.
        # Construct first, then attach it without resetting or reseeding it.
        model = CreditPPO.load(f, device='cpu', force_reset=False)
    model.set_env(env, force_reset=False)
    model.rollout_buffer = CreditBuffer(model.n_steps, model.observation_space, model.action_space,
                                       device='cpu', gamma=model.gamma, gae_lambda=model.gae_lambda, n_envs=model.n_envs)
    if model.num_timesteps != meta['steps'] or model._n_updates != meta['updates']:
        raise ValueError('Checkpoint step/update mismatch')
    # Loading SB3 initializes modules and reseeds RNGs. Restore LAST.
    random.setstate(state['python_rng'])
    np.random.set_state(state['numpy_rng'])
    torch.set_rng_state(state['torch_rng'])
    return model, env, meta

