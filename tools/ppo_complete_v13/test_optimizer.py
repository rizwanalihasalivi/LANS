"""Independent optimizer isolation, KL-stop and complete checkpoint contracts."""
import gymnasium as gym
import numpy as np
import torch
from gymnasium import spaces
from stable_baselines3.common.logger import configure

from .learner import IndependentPPO, optimizer_steps


class TinyTask(gym.Env):
    observation_space = spaces.Box(-5, 5, (3,), np.float32)
    action_space = spaces.Box(-1, 1, (2,), np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        self.state = np.array([0.2, -0.1, 1.0], np.float32)
        return self.state.copy(), {}

    def step(self, action):
        self.t += 1
        self.state[:2] += np.asarray(action, np.float32) * .05
        self.state[2] = 1 - self.t / 4
        reward = -float(np.sum((np.asarray(action) - .35) ** 2) + self.state[0] ** 2)
        return self.state.copy(), reward, self.t == 4, False, {}


def model(**kwargs):
    torch.set_num_threads(1)
    result = IndependentPPO("MlpPolicy", TinyTask(), seed=42, device="cpu", n_steps=8, batch_size=4,
        n_epochs=3, target_kl=None, policy_kwargs=dict(net_arch=dict(pi=[16], vf=[16])), **kwargs)
    result.set_logger(configure(folder=None, format_strings=[]))
    return result


def state_equal(a, b):
    if isinstance(a, torch.Tensor):
        assert torch.equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a: state_equal(a[key], b[key])
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b): state_equal(x, y)
    else:
        assert a == b


def fill_buffer(agent, *, log_prob_offset=0.0):
    buffer = agent.rollout_buffer
    buffer.reset()
    for i in range(agent.n_steps):
        obs = np.array([[.15 + .01 * i, -.1, 1 - (i % 4) / 4]], np.float32)
        with torch.no_grad():
            action, value, log_prob = agent.policy(torch.as_tensor(obs), deterministic=True)
        buffer.add(obs, action.numpy(), np.array([.2 + .01 * i], np.float32), np.array([i % 4 == 0]), value,
                   log_prob + log_prob_offset)
    buffer.compute_returns_and_advantage(torch.zeros(1), np.ones(1, bool))


def test_full_optimizer_checkpoint_and_continued_training(tmp_path):
    agent = model()
    initial_path = tmp_path / "initial.zip"
    agent.save(initial_path)
    initial = IndependentPPO.load(initial_path, device="cpu")
    assert initial.actor_steps == initial.critic_steps == 0
    assert optimizer_steps(initial.actor_optimizer) == optimizer_steps(initial.critic_optimizer) == 0
    agent.learn(total_timesteps=16)
    assert agent.actor_steps == agent.critic_steps == 12
    assert optimizer_steps(agent.policy.optimizer) == 0
    assert agent.last_train["actor_parameter_delta_l2"] > 0
    assert agent.last_train["critic_parameter_delta_l2"] > 0
    path = tmp_path / "full.zip"
    agent.save(path)
    loaded = IndependentPPO.load(path, device="cpu")
    query = np.array([.2, -.1, .5], np.float32)
    np.testing.assert_array_equal(agent.predict(query, deterministic=True)[0], loaded.predict(query, deterministic=True)[0])
    with torch.no_grad():
        assert torch.equal(agent.policy.predict_values(torch.as_tensor(query[None])), loaded.policy.predict_values(torch.as_tensor(query[None])))
    state_equal(agent.actor_optimizer.state_dict(), loaded.actor_optimizer.state_dict())
    state_equal(agent.critic_optimizer.state_dict(), loaded.critic_optimizer.state_dict())
    assert loaded.actor_steps == agent.actor_steps and loaded.critic_steps == agent.critic_steps
    assert loaded.train_history == agent.train_history
    continued = IndependentPPO.load(path, env=TinyTask(), device="cpu")
    continued.learn(total_timesteps=8, reset_num_timesteps=False)
    assert continued.num_timesteps == 24 and continued.actor_steps == continued.critic_steps == 18
    continued.validate_optimizer_counters()


def test_actor_kl_stop_preserves_actor_but_completes_critic_epochs(tmp_path):
    agent = model()
    agent.target_kl = .01
    fill_buffer(agent, log_prob_offset=-2.0)
    actor_before = [p.detach().clone() for p in agent._actor_parameters]
    critic_before = [p.detach().clone() for p in agent._critic_parameters]
    agent.train()
    assert agent.actor_steps == 0 and agent.critic_steps == 6
    assert agent.actor_kl_stops == 1 and agent.last_train["kl_stopped"]
    assert all(torch.equal(a, p) for a, p in zip(actor_before, agent._actor_parameters))
    assert any(not torch.equal(a, p) for a, p in zip(critic_before, agent._critic_parameters))
    assert optimizer_steps(agent.policy.optimizer) == 0
    path = tmp_path / "critic-only.zip"
    agent.save(path)
    loaded = IndependentPPO.load(path, device="cpu")
    assert loaded.actor_steps == 0 and loaded.critic_steps == 6 and loaded.actor_kl_stops == 1
    state_equal(agent.actor_optimizer.state_dict(), loaded.actor_optimizer.state_dict())
    state_equal(agent.critic_optimizer.state_dict(), loaded.critic_optimizer.state_dict())


def test_critic_scale_does_not_change_actor_update():
    a, b = model(), model()
    a.n_epochs = b.n_epochs = 1
    fill_buffer(a)
    fill_buffer(b)
    b.rollout_buffer.returns *= 1e6
    # Advantages stay identical: this isolates gradient clipping/optimizer
    # coupling from the intended effect of different advantage targets.
    np.testing.assert_array_equal(a.rollout_buffer.advantages, b.rollout_buffer.advantages)
    np.random.seed(91)
    a.train()
    np.random.seed(91)
    b.train()
    for x, y in zip(a._actor_parameters, b._actor_parameters):
        assert torch.equal(x, y)
    assert b.last_train["critic_grad_norm_preclip_max"] > 1000 * a.last_train["critic_grad_norm_preclip_max"]
    assert a.last_train["actor_grad_norm_preclip_max"] == b.last_train["actor_grad_norm_preclip_max"]


def test_late_actor_kl_stop_saves_a_mixed_actor_critic_checkpoint(tmp_path,monkeypatch):
    agent=model();agent.target_kl=.01
    original=agent.policy.evaluate_actions;calls=[]
    def abrupt_kl(observations,actions):
        values,log_prob,entropy=original(observations,actions);calls.append(1)
        if len(calls)>1:log_prob=log_prob+2.
        return values,log_prob,entropy
    monkeypatch.setattr(agent.policy,'evaluate_actions',abrupt_kl)
    agent.learn(total_timesteps=8)
    assert agent.actor_steps==1 and agent.critic_steps==6
    assert agent.actor_kl_stops==1 and agent.last_train['kl_stopped']
    assert agent.last_train['actor_parameter_delta_l2']>0
    assert agent.last_train['critic_parameter_delta_l2']>0
    path=tmp_path/'mixed-stop.zip';agent.save(path)
    restored=IndependentPPO.load(path,device='cpu')
    assert restored.actor_steps==1 and restored.critic_steps==6
    assert restored.actor_kl_stops==1 and optimizer_steps(restored.policy.optimizer)==0
    state_equal(agent.actor_optimizer.state_dict(),restored.actor_optimizer.state_dict())
    state_equal(agent.critic_optimizer.state_dict(),restored.critic_optimizer.state_dict())
