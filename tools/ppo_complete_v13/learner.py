"""PPO with independent actor/value optimization and auditable update counts.

The clipped policy objective and rollout collection follow SB3 PPO 2.0. Actor
KL stopping leaves the critic's declared epochs running. The stock
``policy.optimizer`` is reserved and unused; full checkpoints require
``IndependentPPO.load`` because they contain two additional Adam state dicts.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.utils import explained_variance
from torch.nn import functional as F


def optimizer_steps(optimizer: torch.optim.Optimizer) -> int:
    """Actual Adam steps, independently readable from serialized optimizer state."""
    return max((int(s["step"]) for s in optimizer.state.values() if "step" in s), default=0)


def _norm_difference(parameters, previous) -> float:
    return math.sqrt(sum(float(torch.sum((p.detach() - old) ** 2)) for p, old in zip(parameters, previous)))


def _mean(values) -> float:
    return float(np.mean(values)) if values else 0.0


class IndependentPPO(PPO):
    """Continuous flat-observation PPO with disjoint actor and critic parameters.

    Shared trainable feature extractors and gSDE are rejected rather than
    silently allowing one optimizer to alter the other network. The project's
    vector MLP policy uses a parameter-free FlattenExtractor and is supported.
    Initial BC should use its own supervised optimizer; these two optimizers
    then remain pristine until actual on-policy learning starts.
    """

    def __init__(
        self,
        policy,
        env,
        *,
        actor_learning_rate: float = 1e-5,
        critic_learning_rate: float = 1e-4,
        actor_max_grad_norm: float = 0.5,
        critic_max_grad_norm: float = 0.5,
        **kwargs: Any,
    ):
        for name, value in (
            ("actor_learning_rate", actor_learning_rate),
            ("critic_learning_rate", critic_learning_rate),
            ("actor_max_grad_norm", actor_max_grad_norm),
            ("critic_max_grad_norm", critic_max_grad_norm),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
            setattr(self, name, float(value))
        self.actor_steps = 0
        self.critic_steps = 0
        self.actor_kl_stops = 0
        self.last_train = {}
        self.train_history = []
        kwargs.setdefault("learning_rate", critic_learning_rate)
        kwargs.setdefault("n_steps", 1024)
        kwargs.setdefault("batch_size", 128)
        kwargs.setdefault("n_epochs", 10)
        kwargs.setdefault("gamma", 1.0)
        kwargs.setdefault("gae_lambda", 0.95)
        kwargs.setdefault("target_kl", 0.01)
        policy_kwargs = dict(kwargs.pop("policy_kwargs", {}) or {})
        policy_kwargs.setdefault("log_std_init", -2.5)
        kwargs["policy_kwargs"] = policy_kwargs
        super().__init__(policy, env, **kwargs)

    def _setup_model(self) -> None:
        super()._setup_model()
        if not isinstance(self.action_space, spaces.Box) or self.use_sde:
            raise ValueError("IndependentPPO requires a continuous Box policy without gSDE")
        actor, critic = [], []
        for name, parameter in self.policy.named_parameters():
            if name == "log_std" or name.startswith(("mlp_extractor.policy_net.", "action_net.")):
                actor.append(parameter)
            elif name.startswith(("mlp_extractor.value_net.", "value_net.")):
                critic.append(parameter)
            elif parameter.requires_grad:
                raise ValueError(f"Unsupported shared/trainable feature parameter: {name}")
        if not actor or not critic or {id(p) for p in actor} & {id(p) for p in critic}:
            raise ValueError("Disjoint nonempty actor and critic parameter sets required")
        self._actor_parameters = actor
        self._critic_parameters = critic
        self.actor_optimizer = torch.optim.Adam(actor, lr=self.actor_learning_rate, eps=1e-5)
        self.critic_optimizer = torch.optim.Adam(critic, lr=self.critic_learning_rate, eps=1e-5)

    def _excluded_save_params(self):
        return super()._excluded_save_params() + [
            "actor_optimizer", "critic_optimizer", "_actor_parameters", "_critic_parameters"
        ]

    def _get_torch_save_params(self):
        names, variables = super()._get_torch_save_params()
        return names + ["actor_optimizer", "critic_optimizer"], variables

    @classmethod
    def load(cls, *args, **kwargs):
        model = super().load(*args, **kwargs)
        model.validate_optimizer_counters()
        return model

    def validate_optimizer_counters(self) -> None:
        if optimizer_steps(self.actor_optimizer) != self.actor_steps:
            raise ValueError("Actor Adam state and declared actual-step counter disagree")
        if optimizer_steps(self.critic_optimizer) != self.critic_steps:
            raise ValueError("Critic Adam state and declared actual-step counter disagree")
        if optimizer_steps(self.policy.optimizer) != 0:
            raise ValueError("The reserved stock policy.optimizer must remain unused")

    def train(self) -> None:
        self.validate_optimizer_counters()
        self.policy.set_training_mode(True)
        # Fixed, independently declared learning rates; PPO's reserved optimizer
        # and its schedule are deliberately never stepped.
        for group in self.actor_optimizer.param_groups:
            group["lr"] = self.actor_learning_rate
        for group in self.critic_optimizer.param_groups:
            group["lr"] = self.critic_learning_rate
        clip_range = float(self.clip_range(self._current_progress_remaining))
        clip_vf = None if self.clip_range_vf is None else float(self.clip_range_vf(self._current_progress_remaining))
        actor_before = [p.detach().clone() for p in self._actor_parameters]
        critic_before = [p.detach().clone() for p in self._critic_parameters]
        actor_start, critic_start = self.actor_steps, self.critic_steps
        actor_active = True
        stopped = False
        actor_losses, value_losses, entropy_losses = [], [], []
        kls, clips, actor_norms, critic_norms = [], [], [], []

        for _ in range(self.n_epochs):
            for data in self.rollout_buffer.get(self.batch_size):
                if actor_active:
                    _, log_prob, entropy = self.policy.evaluate_actions(data.observations, data.actions)
                    advantages = data.advantages
                    if self.normalize_advantage and len(advantages) > 1:
                        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
                    log_ratio = log_prob - data.old_log_prob
                    ratio = torch.exp(log_ratio)
                    with torch.no_grad():
                        kl = float(((ratio - 1) - log_ratio).mean())
                    if not math.isfinite(kl):
                        raise FloatingPointError("Nonfinite policy KL")
                    kls.append(kl)
                    if self.target_kl is not None and kl > 1.5 * self.target_kl:
                        actor_active = False
                        stopped = True
                        self.actor_kl_stops += 1
                    else:
                        objective = torch.minimum(advantages * ratio, advantages * torch.clamp(ratio, 1 - clip_range, 1 + clip_range))
                        policy_loss = -objective.mean()
                        entropy_loss = -(-log_prob).mean() if entropy is None else -entropy.mean()
                        actor_loss = policy_loss + self.ent_coef * entropy_loss
                        if not torch.isfinite(actor_loss):
                            raise FloatingPointError("Nonfinite actor loss")
                        self.actor_optimizer.zero_grad(set_to_none=True)
                        actor_loss.backward()
                        norm = torch.nn.utils.clip_grad_norm_(self._actor_parameters, self.actor_max_grad_norm, error_if_nonfinite=True)
                        self.actor_optimizer.step()
                        self.actor_steps += 1
                        actor_norms.append(float(norm))
                        actor_losses.append(float(policy_loss.detach()))
                        entropy_losses.append(float(entropy_loss.detach()))
                        clips.append(float(((ratio - 1).abs() > clip_range).float().mean()))

                # Build a separate value graph, after any actor update. A KL stop
                # never removes critic minibatches or epochs from this loop.
                values = self.policy.predict_values(data.observations).flatten()
                values_pred = values if clip_vf is None else data.old_values + torch.clamp(values - data.old_values, -clip_vf, clip_vf)
                value_loss = F.mse_loss(data.returns, values_pred)
                critic_loss = self.vf_coef * value_loss
                if not torch.isfinite(critic_loss):
                    raise FloatingPointError("Nonfinite critic loss")
                self.critic_optimizer.zero_grad(set_to_none=True)
                critic_loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(self._critic_parameters, self.critic_max_grad_norm, error_if_nonfinite=True)
                self.critic_optimizer.step()
                self.critic_steps += 1
                critic_norms.append(float(norm))
                value_losses.append(float(value_loss.detach()))
            # This remains an epoch counter, explicitly distinct from Adam steps.
            self._n_updates += 1

        self.validate_optimizer_counters()
        self.last_train = dict(
            actor_steps=self.actor_steps, critic_steps=self.critic_steps,
            actor_steps_this_rollout=self.actor_steps - actor_start,
            critic_steps_this_rollout=self.critic_steps - critic_start,
            actor_kl_stops=self.actor_kl_stops, kl_stopped=stopped,
            actor_kl_mean=_mean(kls), actor_kl_max=max(kls, default=0.0),
            actor_grad_norm_preclip_mean=_mean(actor_norms), actor_grad_norm_preclip_max=max(actor_norms, default=0.0),
            critic_grad_norm_preclip_mean=_mean(critic_norms), critic_grad_norm_preclip_max=max(critic_norms, default=0.0),
            actor_parameter_delta_l2=_norm_difference(self._actor_parameters, actor_before),
            critic_parameter_delta_l2=_norm_difference(self._critic_parameters, critic_before),
            policy_loss=_mean(actor_losses), value_loss=_mean(value_losses),
            entropy_loss=_mean(entropy_losses), clip_fraction=_mean(clips),
            sb3_epoch_counter=self._n_updates,
        )
        self.train_history.append(dict(self.last_train))
        for name, value in self.last_train.items():
            self.logger.record("train/" + name, value)
        self.logger.record("train/explained_variance", float(explained_variance(self.rollout_buffer.values.flatten(), self.rollout_buffer.returns.flatten())))
        self.logger.record("train/actor_learning_rate", self.actor_learning_rate)
        self.logger.record("train/critic_learning_rate", self.critic_learning_rate)
        self.logger.record("train/clip_range", clip_range)
