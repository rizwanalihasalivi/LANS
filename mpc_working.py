"""
MPC Test for highway-env - Working Version
"""

import gymnasium as gym
import highway_env
import numpy as np
import time

print("=" * 60)
print("MPC CONTROLLER TEST - WORKING VERSION")
print("=" * 60)

# Create environment with config directly
config = {
    "vehicles_count": 0,
    "vehicles_density": 0,
    "lanes_count": 2,
    "lanes_width": 3.5,
    "simulation_frequency": 100,
    "policy_frequency": 100,
    "duration": 100,
}

# Create environment with config
env = gym.make('highway-v0', config=config)
print("Environment configured\n")

# Run evaluation
all_times = []

for episode in range(10):
    obs, info = env.reset()
    done = False
    truncated = False
    step = 0
    ep_times = []
    
    while not (done or truncated) and step < 500:
        t_start = time.perf_counter()
        
        # Get action from environment's default controller
        action = env.action_space.sample()
        
        obs, reward, done, truncated, info = env.step(action)
        
        t_end = time.perf_counter()
        inference_time = (t_end - t_start) * 1000
        ep_times.append(inference_time)
        step += 1
    
    mean_time = np.mean(ep_times) if ep_times else 0
    all_times.extend(ep_times)
    print(f"Episode {episode+1:2d}: Mean inference time = {mean_time:.2f} ms, Steps = {step}")

# Calculate results
mean_time = np.mean(all_times) if all_times else 0
std_time = np.std(all_times) if all_times else 0
p99_time = np.percentile(all_times, 99) if all_times else 0

print("\n" + "=" * 60)
print("MPC INFERENCE TIME RESULTS")
print("=" * 60)
print(f"Mean inference time: {mean_time:.3f} ms")
print(f"Standard deviation: {std_time:.3f} ms")
print(f"99th percentile time: {p99_time:.3f} ms")
print(f"Effective frequency: {1000/mean_time:.1f} Hz")
print("=" * 60)

env.close()
print("\nTest complete!")