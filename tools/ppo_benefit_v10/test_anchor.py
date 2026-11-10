import torch
from stable_baselines3 import PPO
from .train import TrainingEnv
from .anchor import install_anchor


def test_anchor_gradient_runs_during_real_ppo_optimizer_steps():
    env=TrainingEnv()
    try:
        model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,n_epochs=1,seed=42,device='cpu')
        obs=torch.zeros((16,30));targets=torch.full((16,1),.2);weights=torch.ones(16)
        handle,losses=install_anchor(model,obs,targets,weights,42)
        model.learn(total_timesteps=16);handle.remove()
        assert len(losses)==4 and all(x>=0 for x in losses) and model._n_updates==2
    finally:env.close()
