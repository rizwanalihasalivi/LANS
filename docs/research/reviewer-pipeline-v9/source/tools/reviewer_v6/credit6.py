"""Decision-only surrogate ablation; fixed-tick GAE/critic remain unchanged."""
import boot6
from collections import namedtuple
import inspect
import textwrap
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.buffers import RolloutBuffer

class CreditBuffer(RolloutBuffer):
    def reset(self):
        super().reset()
        self.credit=np.ones((self.buffer_size,self.n_envs),dtype=np.float32)
        self.next_credit=np.ones(self.n_envs,dtype=np.float32)
    def add(self,*args,**kwargs):
        self.credit[self.pos]=self.next_credit
        super().add(*args,**kwargs)
    def get(self,batch_size=None):
        if not self.generator_ready:self.credit=self.swap_and_flatten(self.credit)
        yield from super().get(batch_size)
    def _get_samples(self,batch_inds,env=None):
        data=super()._get_samples(batch_inds,env)
        sample=namedtuple('CreditSamples',data._fields+('credit',))
        return sample(*data,self.to_torch(self.credit[batch_inds].flatten()))

class CreditPPO(PPO):
    pass

# Keep the complete SB3 2.0.0 critic, GAE, optimizer and KL implementation.
# Each exact replacement is checked, and the generated train function is
# preserved in the experiment snapshot. No future service information is used.
TRAIN_SOURCE=textwrap.dedent(inspect.getsource(PPO.train))
REPLACEMENTS={
    'advantages = rollout_data.advantages': 'mask = rollout_data.credit > 0\n            advantages = rollout_data.advantages.clone()',
    'if self.normalize_advantage and len(advantages) > 1:': 'if self.normalize_advantage and int(mask.sum()) > 1:',
    'advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)': 'advantages = (advantages - advantages[mask].mean()) / (advantages[mask].std() + 1e-8)',
    'ratio = th.exp(log_prob - rollout_data.old_log_prob)': 'ratio = th.exp(th.where(mask, log_prob - rollout_data.old_log_prob, th.zeros_like(log_prob)))',
    'policy_loss = -th.min(policy_loss_1, policy_loss_2).mean()': 'policy_loss = -th.min(policy_loss_1, policy_loss_2)[mask].mean() if mask.any() else values.sum()*0.',
    'clip_fraction = th.mean((th.abs(ratio - 1) > clip_range).float()).item()': 'clip_fraction = th.mean((th.abs(ratio[mask] - 1) > clip_range).float()).item() if mask.any() else 0.',
    'entropy_loss = -th.mean(-log_prob)': 'entropy_loss = -th.mean(-log_prob[mask]) if mask.any() else values.sum()*0.',
    'entropy_loss = -th.mean(entropy)': 'entropy_loss = -th.mean(entropy[mask]) if mask.any() else values.sum()*0.',
    'log_ratio = log_prob - rollout_data.old_log_prob': 'log_ratio = th.where(mask, log_prob - rollout_data.old_log_prob, th.zeros_like(log_prob))',
    'approx_kl_div = th.mean((th.exp(log_ratio) - 1) - log_ratio).cpu().numpy()': 'approx_kl_div = th.mean(((th.exp(log_ratio) - 1) - log_ratio)[mask]).cpu().numpy() if mask.any() else np.array(0.)',
}
for old,new in REPLACEMENTS.items():
    assert TRAIN_SOURCE.count(old)==1,old
    TRAIN_SOURCE=TRAIN_SOURCE.replace(old,new)
scope=dict(PPO.train.__globals__)
exec(compile(TRAIN_SOURCE,'<frozen-credit-surrogate>','exec'),scope)
CreditPPO.train=scope['train']
