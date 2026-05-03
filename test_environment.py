"""
test_environment.py - Diagnostic test for environment
"""

import sys
sys.path.insert(0, '.')
import numpy as np
from envs.path_tracking_env import PathTrackingEnv

print("="*60)
print("ENVIRONMENT DIAGNOSTIC TEST")
print("="*60)

env = PathTrackingEnv(mode='eval')
env.vx = 25.0
env.reset()

print("\nStep | e_y (error) | e_psi (heading) | x_position")
print("-" * 55)

for i in range(20):
    steering = np.array([0.0])  # Zero steering
    obs, reward, terminated, truncated, info = env.step(steering)
    print(f"{i+1:4d} | {info['error']:10.4f} | {info['heading_error']:10.4f} | {info['x_phys']:8.2f}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)

# Also print observation to see normalized values
print("\nSample observation (first 5 steps):")
print("o_t = [e_y, e_y_dot, e_psi, e_psi_dot, vx, preview1-4, tau, tau_pred]")