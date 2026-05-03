# test_correct_path.py
import numpy as np
from envs.path_tracking_env import PathTrackingEnv

# Try different ways to set the path
print("=" * 60)
print("FINDING CORRECT PATH CONFIGURATION")
print("=" * 60)

# Method 1: Check if path_type parameter exists
env = PathTrackingEnv(mode='eval', path_type='double_lane_change')
print("Method 1: Created with path_type='double_lane_change'")

# Method 2: Check config
if hasattr(env, 'config'):
    print(f"Config: {env.config}")

# Method 3: Try to set path after creation
if hasattr(env, 'set_path'):
    env.set_path('iso_3888_2')
    print("Method 3: Used set_path()")

# Method 4: Check the scenarios folder
import os
if os.path.exists('scenarios/double_lane_change.py'):
    print("Method 4: Double lane change scenario exists in scenarios/")

# Run a few steps to see the path
env.reset()
positions = []
for i in range(100):
    if hasattr(env, 'vehicle'):
        positions.append(env.vehicle.position[1] if hasattr(env.vehicle, 'position') else 0)
    action = np.array([0.0])
    result = env.step(action)

print(f"\nLateral positions range: {min(positions):.2f} to {max(positions):.2f} m")

if max(positions) - min(positions) > 1:
    print("✅ Double lane change ACTIVE!")
else:
    print("❌ Still on straight path. Need to fix environment configuration.")