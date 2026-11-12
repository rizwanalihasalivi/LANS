"""Training orchestration invariants with real networks and small synthetic tasks."""
import json
from collections import Counter

import gymnasium as gym
import numpy as np
import torch
from gymnasium import spaces

from . import train
from .learner import IndependentPPO, optimizer_steps


class FlatTask(gym.Env):
    observation_space = spaces.Box(-5, 5, (55,), np.float32)
    action_space = spaces.Box(-1, 1, (8,), np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(55, np.float32), {}

    def step(self, action):
        return np.zeros(55, np.float32), -1., True, False, {}


def small_model():
    torch.set_num_threads(1)
    return IndependentPPO("MlpPolicy", FlatTask(), seed=42, device="cpu",
        n_steps=8, batch_size=4, n_epochs=3,
        policy_kwargs=dict(net_arch=dict(pi=[16], vf=[16])))


def test_complete_episode_warmup_targets_and_actor_identity(tmp_path, monkeypatch):
    expected = {}
    class CompleteEpisodes:
        def __init__(self, trace, **kwargs):
            self.trace = trace.open('x')
            self.episode = -1
            self.seed_seen = None

        def reset(self, *, seed=None):
            if seed is not None:
                assert seed == 90042
                self.seed_seen = seed
            self.episode += 1
            self.tick = 0
            self.length = 4 + self.episode % 2
            self.done = False
            self.rewards = [float(i + 1) for i in range(self.length)]
            if self.episode % 2:
                # A shortened failed episode has a real terminal penalty;
                # it is not dropped or bootstrapped from a subsequent episode.
                self.rewards[-1] = -20.
            for i in range(self.length):
                expected[self.episode * 10 + i] = sum(self.rewards[i:])
            return self.observation(), {}

        def observation(self):
            value = np.zeros(55, np.float32)
            value[0] = self.episode * 10 + self.tick
            return value

        def step(self, action):
            reward = self.rewards[self.tick]
            self.tick += 1
            self.done = self.tick == self.length
            self.trace.write(json.dumps(dict(episode=self.episode, reward=reward))+'\n')
            return self.observation(), reward, self.done, False, {
                'terminal_reason': 'failure' if self.done and self.episode % 2 else 'horizon' if self.done else ''}

        def close(self):
            assert self.episode == 31 and self.done and self.seed_seen == 90042
            self.trace.close()

    monkeypatch.setattr(train, 'Env', CompleteEpisodes)
    model = small_model()
    before = train.actor_digest(model)
    critic_before = [p.detach().clone() for p in model._critic_parameters]
    observed = Counter()
    current_ids = []
    predict = model.policy.predict_values
    loss = torch.nn.functional.mse_loss
    def capture_predict(x):
        current_ids[:] = x[:, 0].detach().cpu().numpy().astype(int).tolist()
        return predict(x)
    def capture_loss(predicted, target, *args, **kwargs):
        for index, value in zip(current_ids, target.detach().cpu().numpy()):
            assert value == expected[index]
            observed[index] += 1
        return loss(predicted, target, *args, **kwargs)
    monkeypatch.setattr(model.policy, 'predict_values', capture_predict)
    monkeypatch.setattr(torch.nn.functional, 'mse_loss', capture_loss)
    report = train.critic_warmup(model, 42, tmp_path)
    assert report['episodes'] == 32 and report['environment_steps'] == 144
    assert report['failures'] == 16 and report['critic_updates'] == 8
    assert observed == Counter({key: 4 for key in expected})
    assert train.actor_digest(model) == before
    assert model.actor_steps == model.num_timesteps == 0
    assert optimizer_steps(model.actor_optimizer) == optimizer_steps(model.policy.optimizer) == 0
    assert model.critic_steps == optimizer_steps(model.critic_optimizer) == 8
    assert any(not torch.equal(a, b) for a, b in zip(critic_before, model._critic_parameters))
    model.validate_optimizer_counters()


def test_continued_bc_uses_seed_actual_actor_step_budget_only(tmp_path, monkeypatch):
    monkeypatch.setattr(train, 'DATA', tmp_path)
    monkeypatch.setattr(train, 'snapshot', lambda output: {})
    source = tmp_path/'policies/seed-42'
    source.mkdir(parents=True)
    model = small_model()
    before = train.actor_digest(model)
    critic_before = [p.detach().clone() for p in model._critic_parameters]
    model.save(source/'bc-policy.zip')
    (source/'manifest.json').write_text(json.dumps(dict(actor_steps=7)))
    dataset = tmp_path/'dataset'
    dataset.mkdir()
    rng = np.random.default_rng(123)
    np.savez_compressed(dataset/'dataset.npz',
        observations=rng.uniform(-1, 1, (13, 55)).astype(np.float32),
        actions=np.full((13, 8), .35, np.float32), weights=np.ones(13, np.float32))
    actual_steps = []
    step = torch.optim.Adam.step
    def count_step(optimizer, *args, **kwargs):
        actual_steps.append(1)
        return step(optimizer, *args, **kwargs)
    monkeypatch.setattr(torch.optim.Adam, 'step', count_step)
    result = train.continued_worker(42)
    assert result['supervised_optimizer_steps'] == len(actual_steps) == 7
    assert result['steps'] == result['actor_ppo_steps'] == 0
    supervised = torch.load(tmp_path/'continued-bc/seed-42/supervised-optimizer.pt', map_location='cpu')
    assert max(int(value['step']) for value in supervised['state'].values()) == 7
    assert result['supervised_optimizer_sha256'] == train.sha(tmp_path/'continued-bc/seed-42/supervised-optimizer.pt')
    restored = IndependentPPO.load(tmp_path/'continued-bc/seed-42/policy.zip', device='cpu')
    assert train.actor_digest(restored) != before
    assert all(torch.equal(a, b) for a, b in zip(critic_before, restored._critic_parameters))
    assert restored.actor_steps == restored.critic_steps == restored.num_timesteps == 0
    restored.validate_optimizer_counters()
