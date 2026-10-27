"""Fixed-budget PPO with exact update-boundary resume and explicit exploration arm."""
import boot12
import json
import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from credit6 import CreditPPO, CreditBuffer
from env12 import Env
from checkpoint12 import save, load, atomic_json

P = json.loads((boot12.HERE/'protocol.json').read_text())


def initialize(pair, arm):
    cfg = P['training']; seed = cfg['seeds'][pair]
    old = boot12.ROOT/f'docs/research/reviewer-training-v11/training-{pair}'
    vec = DummyVecEnv([lambda slot=slot: Env(pair=pair, slot=slot, seed=seed+slot,
                         source='newppo', training_noise_base=cfg['noise_base']) for slot in range(4)])
    env = VecNormalize.load(old/'reward-normalization.pkl', vec)
    env.training = True; env.norm_obs = False
    with (old/'policy.zip').open('rb') as f:
        model = CreditPPO.load(f, env=env, device='cpu', force_reset=True)
    if arm == 'explore':
        with torch.no_grad():
            for param in model.policy.action_net.parameters():
                param.mul_(.25)
                model.policy.optimizer.state.pop(param, None)
    elif arm != 'continued':
        raise ValueError(arm)
    model.seed = seed; model.set_random_seed(seed)
    model.rollout_buffer = CreditBuffer(model.n_steps, model.observation_space, model.action_space,
                                       device='cpu', gamma=model.gamma, gae_lambda=model.gae_lambda, n_envs=4)
    model.audit_counts = dict(submitted=0, active=0)
    return model, env


class Credit(BaseCallback):
    def _on_step(self):
        infos = self.locals['infos']
        mask = np.array([i['submitted'] for i in infos], np.float32)
        self.model.rollout_buffer.next_credit = mask
        self.model.audit_counts['submitted'] += int(mask.sum())
        self.model.audit_counts['active'] += sum(abs(i['command']-i['baseline']) > 1e-10 for i in infos)
        return True


def train(pair, arm, out, signature, publish=None):
    out.mkdir(parents=True, exist_ok=True)
    checkpoints = out/'checkpoints'
    cfg = P['training']; total = cfg['steps_each']
    resumed = (checkpoints/'latest.json').exists()
    if resumed:
        model, env, _ = load(checkpoints, signature)
    else:
        model, env = initialize(pair, arm)
    model.set_logger(configure(None, []))
    callback = Credit()
    remaining = total-model.num_timesteps if resumed else total
    if remaining < 0:
        raise ValueError('Checkpoint beyond declared training budget')
    if remaining or not resumed:
        _, callback = model._setup_learn(remaining, callback, reset_num_timesteps=not resumed)
    else:
        callback.init_callback(model)
    if not resumed:
        save(model, checkpoints, signature)
    while model.num_timesteps < total:
        if not model.collect_rollouts(env, callback, model.rollout_buffer, model.n_steps):
            raise RuntimeError('Incomplete rollout')
        model._update_current_progress_remaining(model.num_timesteps, total)
        model.train()
        if model.num_timesteps % cfg['checkpoint_steps'] == 0:
            snapshot = save(model, checkpoints, signature)
            stats = {k: float(v) for k, v in model.logger.name_to_value.items() if np.isscalar(v)}
            progress = dict(arm=arm, pair=pair, additional_steps=model.num_timesteps,
                            updates=model._n_updates, **model.audit_counts, optimizer=stats,
                            snapshot=str(snapshot.relative_to(out)))
            atomic_json(out/f'progress-{model.num_timesteps}.json', progress)
            print(json.dumps(progress), flush=True)
            if publish is not None: publish(f'Save v12 {arm} pair {pair} at {model.num_timesteps} steps')
    assert model.num_timesteps == total
    latest = json.loads((checkpoints/'latest.json').read_text())
    atomic_json(out/'complete.json', dict(arm=arm, pair=pair, additional_steps=total,
                                         **model.audit_counts, checkpoint=latest, endpoint_eligible=True))
    env.close()
    return latest
