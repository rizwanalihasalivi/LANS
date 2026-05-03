"""
collect_lans_data.py - Collect real LANS trajectory data
"""

import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv

print("="*60)
print("COLLECTING LANS TRAJECTORY DATA")
print("="*60)

# LQR gains
K_LQR = np.array([0.52, 0.12, 0.31, 0.04])

def adaptive_gain(tau):
    """β(τ) adaptive gain"""
    if tau < 5:
        return 1.0
    else:
        return np.exp(-(tau - 5) / 20)

# Setup
raw_env = PathTrackingEnv(mode='eval')
raw_env.vx = 25.0
raw_env.K_lqr = K_LQR

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

data = {'x': [], 'y_actual': [], 'y_ref': [], 'error': [], 'latency': [], 'beta': []}

for step in range(len(raw_env.y_ref) - 1):
    t_start = time.perf_counter()
    
    error_state = raw_env.state if hasattr(raw_env, 'state') else np.zeros(4)
    delta_lqr = -np.dot(K_LQR, error_state)
    delta_lqr = np.clip(delta_lqr, -0.5, 0.5)
    
    action, _ = model.predict(obs, deterministic=True)
    delta_rl = action[0]
    
    t_end = time.perf_counter()
    tau = (t_end - t_start) * 1000
    beta = adaptive_gain(tau)
    
    delta_total = delta_lqr + beta * delta_rl
    delta_total = np.clip(delta_total, -0.5, 0.5)
    
    obs, _, _, info = env.step(np.array([delta_total]))
    
    data['x'].append(info[0]['x_phys'])
    data['y_actual'].append(info[0]['y_phys'])
    data['y_ref'].append(raw_env.y_ref[raw_env.t_step])
    data['error'].append(info[0]['error'])
    data['latency'].append(tau)
    data['beta'].append(beta)

# Save to CSV
df = pd.DataFrame(data)
df.to_csv('real_data/lans_trajectory.csv', index=False)

# Calculate metrics
rmse = np.sqrt(np.mean(np.square(data['error'])))
mean_latency = np.mean(data['latency'])
mean_beta = np.mean(data['beta'])

print(f"Saved {len(df)} steps to real_data/lans_trajectory.csv")
print(f"LANS RMSE: {rmse:.4f} m")
print(f"Mean latency: {mean_latency:.2f} ms")
print(f"Mean beta: {mean_beta:.3f}")
print("="*60)