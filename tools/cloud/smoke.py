import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import torch
from stable_baselines3 import PPO
from envs.path_tracking_env import PathTrackingEnv
from envs.residual_path_env import ResidualPathEnv
from controllers.lans_controller import LANSController

torch.set_num_threads(2)
out = Path('/workspace/lans-setup/output')
out.mkdir(exist_ok=True)
controller = LANSController(load_ppo_model=False)
steer, info = controller.step(1.2, 1., .05, .02, .1, .05, .01)
assert np.isfinite(steer) and abs(steer) <= .5
assert info['observation'].shape == (11,)
for cls in (PathTrackingEnv, ResidualPathEnv):
    env = cls()
    obs, _ = env.reset(seed=42)
    assert env.observation_space.contains(obs)
    for i in range(100):
        obs, reward, done, truncated, info = env.step(np.array([.01], dtype=np.float32))
        assert env.observation_space.contains(obs) and np.isfinite(reward)
        if done or truncated:
            env.reset(seed=42)
    model = PPO('MlpPolicy', env, n_steps=64, batch_size=32, n_epochs=2,
                seed=42, device='cpu', verbose=0)
    model.learn(total_timesteps=128)
    target = out / cls.__name__
    model.save(target)
    loaded = PPO.load(target, env=env, device='cpu')
    obs, _ = env.reset(seed=42)
    action, _ = loaded.predict(obs, deterministic=True)
    assert env.action_space.contains(action)
    obs, reward, *_ = env.step(action)
    assert np.isfinite(obs).all() and np.isfinite(reward)
    env.close()
    print(f'{cls.__name__}: 100 simulation steps, 128 PPO training steps, save/load/predict PASS')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.plot([0, 1], [0, steer])
plt.savefig(out / 'smoke.png')
print('Controller and headless plotting PASS')
