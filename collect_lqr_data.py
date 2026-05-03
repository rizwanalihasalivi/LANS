"""
collect_lqr_data.py - Collect real LQR trajectory data
"""

import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from envs.path_tracking_env import PathTrackingEnv
from controllers.lqr_controller import get_lqr_controller

print("="*60)
print("COLLECTING LQR TRAJECTORY DATA")
print("="*60)

# Setup
env = PathTrackingEnv(mode='eval')
env.vx = 25.0
env.reset()

# Get LQR controller
K_lqr, lqr_control = get_lqr_controller(vx=25.0)

# Store data
data = {'x': [], 'y_actual': [], 'y_ref': [], 'error': []}

for step in range(len(env.y_ref) - 1):
    error_state = env.state if hasattr(env, 'state') else np.zeros(4)
    steering = lqr_control(error_state)
    _, _, _, _, info = env.step(np.array([steering]))
    
    data['x'].append(info['x_phys'])
    data['y_actual'].append(info['y_phys'])
    data['y_ref'].append(info['y_ref'])
    data['error'].append(info['error'])

# Save to CSV
df = pd.DataFrame(data)
df.to_csv('real_data/lqr_trajectory.csv', index=False)

# Calculate RMSE
rmse = np.sqrt(np.mean(np.square(data['error'])))
print(f"Saved {len(df)} steps to real_data/lqr_trajectory.csv")
print(f"LQR RMSE: {rmse:.4f} m")
print("="*60)