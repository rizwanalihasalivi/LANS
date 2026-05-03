"""
test_dynamics.py - Check if vehicle dynamics are working
"""

import sys
sys.path.insert(0, '.')
import numpy as np
from envs.path_tracking_env import PathTrackingEnv

print("="*60)
print("DYNAMICS DIAGNOSTIC")
print("="*60)

env = PathTrackingEnv(mode='eval')
env.vx = 25.0
env.reset()

print("\n1. Checking A and B matrices:")
print(f"   A matrix shape: {env.A.shape}")
print(f"   A matrix:\n{env.A}")
print(f"   B matrix: {env.B}")

print("\n2. Checking discretized matrices:")
print(f"   A_d shape: {env.A_d.shape}")
print(f"   A_d:\n{env.A_d}")
print(f"   B_d: {env.B_d}")

# Manually set an initial error
print("\n3. Manual test with initial error:")
env.state = np.array([0.5, 0.0, 0.1, 0.0])  # 0.5m error, 0.1rad heading
print(f"   Initial state: e_y={env.state[0]:.3f}, e_psi={env.state[2]:.3f}")

# Apply zero steering
steering = np.array([0.0])
obs, reward, terminated, truncated, info = env.step(steering)

print(f"   After 1 step: e_y={info['error']:.4f}, e_psi={info['heading_error']:.4f}")
print(f"   x_position: {info['x_phys']:.2f}m")

# Check if state changed
print(f"   New state: {env.state}")

# Multiple steps with initial error
print("\n4. Multiple steps with initial error:")
env.reset()
env.state = np.array([0.5, 0.0, 0.1, 0.0])
print("Step | e_y | e_psi | x_pos")
print("-" * 40)

for i in range(10):
    obs, reward, terminated, truncated, info = env.step(np.array([0.0]))
    print(f"{i+1:4d} | {info['error']:6.4f} | {info['heading_error']:6.4f} | {info['x_phys']:6.2f}")

print("\n" + "="*60)
print("If errors remain constant, dynamics are NOT working!")
print("="*60)