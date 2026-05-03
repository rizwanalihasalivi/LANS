"""
collect_ppo_data.py - Collect real PPO trajectory data
"""

import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv

print("="*60)
print("COLLECTING PPO TRAJECTORY DATA")
print("="*60)

# Setup
raw_env = PathTrackingEnv(mode='eval')
raw_env.vx = 25.0
env = DummyVecEnv([lambda: raw_env])

try:
    env = VecNormalize.load('models/vec_normalize_curriculum_final.pkl', env)
    env.training = False
    env.norm_reward = False
    print("Loaded normalization")
except:
    print("No normalization found")

model = PPO.load('models/ppo_curriculum_final')
obs = env.reset()

data = {'x': [], 'y_actual': [], 'y_ref': [], 'error': []}

for step in range(len(raw_env.y_ref) - 1):
    action, _ = model.predict(obs, deterministic=True)
    obs, _, _, info = env.step(action)
    
    data['x'].append(info[0]['x_phys'])
    data['y_actual'].append(info[0]['y_phys'])
    data['y_ref'].append(raw_env.y_ref[raw_env.t_step])
    data['error'].append(info[0]['error'])

# Save to CSV
df = pd.DataFrame(data)
df.to_csv('real_data/ppo_trajectory.csv', index=False)

# Calculate RMSE
rmse = np.sqrt(np.mean(np.square(data['error'])))
print(f"Saved {len(df)} steps to real_data/ppo_trajectory.csv")
print(f"PPO RMSE: {rmse:.4f} m")
print("="*60)