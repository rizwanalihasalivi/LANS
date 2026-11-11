import pytest
import torch
from stable_baselines3 import PPO
from .learning import Env
from .damped import install_damping,optimizer_steps


def test_damping_changes_only_actor_step_and_preserves_loadable_optimizer(tmp_path):
    env=Env()
    try:
        model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,seed=42,device='cpu',learning_rate=1e-4)
        actor=model.policy.action_net.bias;critic=model.policy.value_net.bias
        before_a=actor.detach().clone();before_c=critic.detach().clone()
        for p in model.policy.parameters():p.grad=torch.ones_like(p)
        handles,counts=install_damping(model);model.policy.optimizer.step()
        for h in handles:h.remove()
        da=(actor-before_a).detach();dc=(critic-before_c).detach()
        assert float(da[0]/dc[0])==pytest.approx(.01,rel=1e-5)
        assert counts[0]==optimizer_steps(model)==1
        model.save(tmp_path/'policy.zip');loaded=PPO.load(tmp_path/'policy.zip',device='cpu')
        assert optimizer_steps(loaded)==1
    finally:env.close()
