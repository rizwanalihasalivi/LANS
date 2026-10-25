"""SB3 2.0.0 PPO.train (MIT, DLR-RM contributors), with two explicit changes:
fixed-student KL regularization and optional in-flight action-gradient masking.
Value fitting remains on every transition. No adaptive anchor/reward search.
"""
import numpy as np
import torch as th
from torch.nn import functional as F
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.utils import explained_variance
from bootstrap import RESEARCH
from policy10 import FrozenStudent,logits


class AnchoredPPO(PPO):
    def __init__(self,*args,anchor_coef=0.,mask_busy=False,student_seed=701,**kwargs):
        self.anchor_coef=anchor_coef;self.mask_busy=mask_busy;self.student_seed=student_seed
        super().__init__(*args,**kwargs)
    def _setup_model(self):
        super()._setup_model()
        self.anchor_ref=None;self.anchor_pool=None
        if self.anchor_coef:
            with th.random.fork_rng(devices=[]):
                self.anchor_ref=FrozenStudent(RESEARCH.parent/f'results/revision8-student/students/{self.student_seed}').to(self.device)
            self.anchor_ref.requires_grad_(False)
            self.anchor_pool=np.load(RESEARCH.parent/'results/revision8-student/data/train.npz')['x']
        if not hasattr(self,'anchor_rng'):self.anchor_rng=np.random.default_rng(self.seed+90000000)
    def _excluded_save_params(self):return super()._excluded_save_params()+['anchor_ref','anchor_pool']
    def decision_mask(self,obs):
        if not self.mask_busy:return th.ones(obs.shape[0],device=obs.device)
        return ((obs[:,17]<.5)|(obs[:,15]<=1e-8)).float()
    @staticmethod
    def weighted_mean(values,mask):return (values*mask).sum()/mask.sum().clamp(min=1.)
    def anchor_loss(self,obs):
        if not self.anchor_coef:return obs.new_zeros(())
        indices=self.anchor_rng.integers(0,len(self.anchor_pool),size=len(obs))
        replay=th.as_tensor(self.anchor_pool[indices],device=self.device)
        mixed=th.cat((obs,replay))
        with th.no_grad():reference=self.anchor_ref(mixed).log_softmax(1)
        current=logits(self,mixed).log_softmax(1)
        return (reference.exp()*(reference-current)).sum(1).mean()

    def train(self) -> None:
        """
        Update policy using the currently gathered rollout buffer.
        """
        # Switch to train mode (this affects batch norm / dropout)
        self.policy.set_training_mode(True)
        # Update optimizer learning rate
        self._update_learning_rate(self.policy.optimizer)
        # Compute current clip range
        clip_range = self.clip_range(self._current_progress_remaining)  # type: ignore[operator]
        # Optional: clip range for the value function
        if self.clip_range_vf is not None:
            clip_range_vf = self.clip_range_vf(self._current_progress_remaining)  # type: ignore[operator]

        anchor_losses = []
        entropy_losses = []
        pg_losses, value_losses = [], []
        clip_fractions = []

        continue_training = True
        # train for n_epochs epochs
        for epoch in range(self.n_epochs):
            approx_kl_divs = []
            # Do a complete pass on the rollout buffer
            for rollout_data in self.rollout_buffer.get(self.batch_size):
                actions = rollout_data.actions
                if isinstance(self.action_space, spaces.Discrete):
                    # Convert discrete action from float to long
                    actions = rollout_data.actions.long().flatten()

                # Re-sample the noise matrix because the log_std has changed
                if self.use_sde:
                    self.policy.reset_noise(self.batch_size)

                values, log_prob, entropy = self.policy.evaluate_actions(rollout_data.observations, actions)
                values = values.flatten()
                mask = self.decision_mask(rollout_data.observations)
                # Normalize advantage
                advantages = rollout_data.advantages
                # Normalization does not make sense if mini batchsize == 1, see GH issue #325
                selected = advantages[mask.bool()]
                if self.normalize_advantage and len(selected) > 1:
                    advantages = (advantages - selected.mean()) / (selected.std() + 1e-8)

                # ratio between old and new policy, should be one at the first iteration
                ratio = th.exp(log_prob - rollout_data.old_log_prob)

                # clipped surrogate loss
                policy_loss_1 = advantages * ratio
                policy_loss_2 = advantages * th.clamp(ratio, 1 - clip_range, 1 + clip_range)
                policy_loss = -self.weighted_mean(th.min(policy_loss_1, policy_loss_2), mask)

                # Logging
                pg_losses.append(policy_loss.item())
                clip_fraction = th.mean((th.abs(ratio - 1) > clip_range).float()).item()
                clip_fractions.append(clip_fraction)

                if self.clip_range_vf is None:
                    # No clipping
                    values_pred = values
                else:
                    # Clip the difference between old and new value
                    # NOTE: this depends on the reward scaling
                    values_pred = rollout_data.old_values + th.clamp(
                        values - rollout_data.old_values, -clip_range_vf, clip_range_vf
                    )
                # Value loss using the TD(gae_lambda) target
                value_loss = F.mse_loss(rollout_data.returns, values_pred)
                value_losses.append(value_loss.item())

                # Entropy loss favor exploration
                if entropy is None:
                    # Approximate entropy when no analytical form
                    entropy_loss = -self.weighted_mean(-log_prob, mask)
                else:
                    entropy_loss = -self.weighted_mean(entropy, mask)

                entropy_losses.append(entropy_loss.item())

                anchor_loss = self.anchor_loss(rollout_data.observations)
                anchor_losses.append(anchor_loss.item())
                loss = policy_loss + self.ent_coef * entropy_loss + self.vf_coef * value_loss + self.anchor_coef * anchor_loss

                # Calculate approximate form of reverse KL Divergence for early stopping
                # see issue #417: https://github.com/DLR-RM/stable-baselines3/issues/417
                # and discussion in PR #419: https://github.com/DLR-RM/stable-baselines3/pull/419
                # and Schulman blog: http://joschu.net/blog/kl-approx.html
                with th.no_grad():
                    log_ratio = log_prob - rollout_data.old_log_prob
                    approx_kl_div = th.mean((th.exp(log_ratio) - 1) - log_ratio).cpu().numpy()
                    approx_kl_divs.append(approx_kl_div)

                if self.target_kl is not None and approx_kl_div > 1.5 * self.target_kl:
                    continue_training = False
                    if self.verbose >= 1:
                        print(f"Early stopping at step {epoch} due to reaching max kl: {approx_kl_div:.2f}")
                    break

                # Optimization step
                self.policy.optimizer.zero_grad()
                loss.backward()
                # Clip grad norm
                th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.policy.optimizer.step()

            self._n_updates += 1
            if not continue_training:
                break

        explained_var = explained_variance(self.rollout_buffer.values.flatten(), self.rollout_buffer.returns.flatten())

        # Logs
        self.logger.record("train/student_anchor_kl", np.mean(anchor_losses))
        self.logger.record("train/entropy_loss", np.mean(entropy_losses))
        self.logger.record("train/policy_gradient_loss", np.mean(pg_losses))
        self.logger.record("train/value_loss", np.mean(value_losses))
        self.logger.record("train/approx_kl", np.mean(approx_kl_divs))
        self.logger.record("train/clip_fraction", np.mean(clip_fractions))
        self.logger.record("train/loss", loss.item())
        self.logger.record("train/explained_variance", explained_var)
        if hasattr(self.policy, "log_std"):
            self.logger.record("train/std", th.exp(self.policy.log_std).mean().item())

        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/clip_range", clip_range)
        if self.clip_range_vf is not None:
            self.logger.record("train/clip_range_vf", clip_range_vf)
