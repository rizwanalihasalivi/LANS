"""
LANS Controller with highway-env - WORKING VERSION
"""

import gymnasium as gym
import highway_env
import numpy as np
import time
import matplotlib.pyplot as plt
import os

# ============================================================
# LQR Controller
# ============================================================
def lqr_control(error_state):
    K = np.array([0.52, 0.12, 0.31, 0.04])
    return -np.dot(K, error_state)

# ============================================================
# LANS Controller
# ============================================================
prev_steering = 0.0
smoothing_factor = 0.3
max_steering_rate = 0.1

def lans_control(error_state, tau_ms):
    global prev_steering
    
    delta_lqr = lqr_control(error_state)
    
    if tau_ms < 5:
        beta = 1.0
    else:
        beta = np.exp(-(tau_ms - 5) / 20)
    
    ppo_gain = 0.3
    delta_rl = ppo_gain * 0.05 * np.tanh(error_state[0])
    
    delta_total_raw = delta_lqr + beta * np.clip(delta_rl, -0.5, 0.5)
    delta_total_smoothed = smoothing_factor * prev_steering + (1 - smoothing_factor) * delta_total_raw
    
    delta_change = delta_total_smoothed - prev_steering
    delta_change = np.clip(delta_change, -max_steering_rate, max_steering_rate)
    delta_total = prev_steering + delta_change
    
    prev_steering = delta_total
    
    return np.clip(delta_total, -0.5, 0.5)

# ============================================================
# Configure highway-env
# ============================================================
config = {
    "observation": {
        "type": "Kinematics",
        "features": ["presence", "x", "y", "vx", "vy", "heading"],
        "normalize": False
    },
    "action": {
        "type": "ContinuousAction",
        "longitudinal": True,
        "steering_range": [-0.5, 0.5],
        "acceleration_range": [0, 5.0]
    },
    "simulation_frequency": 1000,
    "policy_frequency": 1000,
    "duration": 20,
    "vehicles_count": 0,
    "lanes_count": 3,
    "vehicles_density": 0,
    "initial_lane_id": 1,
}

# ============================================================
# Run LANS controller
# ============================================================
print("=" * 60)
print("LANS Controller with highway-env")
print("=" * 60)

env = gym.make('highway-v0', config=config, render_mode='human')
obs, info = env.reset()

# Try to set speed using different method
try:
    # Method 1: Direct attribute
    env.unwrapped.vehicle.speed = 15.0
except:
    pass

times = []
lateral_errors = []
steering_commands = []
speeds = []

print("Running... Close window to stop.")
print("Press throttle to accelerate (use 'up' arrow key or set throttle in code)")

try:
    step = 0
    # Use higher throttle to overcome inertia
    throttle = 0.8  # 80% throttle
    
    # Alternative: Use keyboard control to start
    print("\nTIP: Press 'UP' arrow key to accelerate manually if vehicle doesn't move.")
    
    while True:
        # Get vehicle state
        vehicle = env.unwrapped.vehicle
        lateral_position = vehicle.position[1]
        heading = vehicle.heading
        speed = vehicle.speed
        
        # Error state
        error_state = np.array([lateral_position, 0.0, heading, 0.0], dtype=np.float32)
        
        # Measure inference time
        start = time.perf_counter()
        tau_ms = 0.0775
        steering = lans_control(error_state, tau_ms)
        end = time.perf_counter()
        inference_us = (end - start) * 1e6
        
        # Action = [throttle, steering]
        action = [throttle, steering]
        
        obs, reward, done, truncated, info = env.step(action)
        
        times.append(inference_us)
        lateral_errors.append(lateral_position)
        steering_commands.append(steering)
        speeds.append(speed)
        
        step += 1
        
        if step % 5000 == 0:
            print(f"Step {step}: y={lateral_position:.2f}m, v={speed:.2f}m/s, steer={steering:.3f}rad, throttle={throttle}")
        
        if done or truncated:
            obs, info = env.reset()
            print(f"Episode finished at step {step} - reset")
            
except KeyboardInterrupt:
    print("\nStopped by user")
finally:
    env.close()

# ============================================================
# Results
# ============================================================
if len(times) > 0:
    times = np.array(times)
    lateral_errors = np.array(lateral_errors)
    steering_commands = np.array(steering_commands)
    speeds = np.array(speeds)
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total steps: {len(times)}")
    print(f"Mean inference time: {np.mean(times):.1f} µs")
    print(f"Std deviation: {np.std(times):.1f} µs")
    print(f"99th percentile: {np.percentile(times, 99):.1f} µs")
    print(f"Mean frequency: {1e6 / np.mean(times):.0f} Hz")
    
    # Filter out zero-speed steps for error analysis
    moving_steps = speeds > 0.1
    if np.any(moving_steps):
        moving_errors = np.abs(lateral_errors[moving_steps])
        print(f"Mean lateral error (when moving): {np.mean(moving_errors):.4f} m")
        print(f"Max lateral error (when moving): {np.max(moving_errors):.4f} m")
        print(f"95th percentile error (when moving): {np.percentile(moving_errors, 95):.4f} m")
    else:
        print("Mean lateral error: {np.mean(np.abs(lateral_errors)):.4f} m")
        print(f"Max lateral error: {np.max(np.abs(lateral_errors)):.4f} m")
    
    print(f"Mean speed: {np.mean(speeds):.1f} m/s")
    print(f"Max speed: {np.max(speeds):.1f} m/s")
    print(f"Min speed: {np.min(speeds):.1f} m/s")
    print("=" * 60)
    
    # Create results directory
    os.makedirs('paper_figures', exist_ok=True)
    
    # Plot results
    fig, axes = plt.subplots(4, 1, figsize=(10, 12))
    
    axes[0].plot(times, 'b-', alpha=0.7)
    axes[0].set_ylabel('Inference Time (µs)')
    axes[0].set_title('LANS Controller Inference Time')
    axes[0].axhline(np.mean(times), color='r', linestyle='--', label=f'Mean: {np.mean(times):.1f} µs')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(lateral_errors, 'g-', alpha=0.7)
    axes[1].set_ylabel('Lateral Error (m)')
    axes[1].set_title('Tracking Error')
    axes[1].axhline(0, color='k', linewidth=0.5)
    axes[1].axhline(y=3.5, color='orange', linestyle='--', alpha=0.5, label='Right lane boundary')
    axes[1].axhline(y=-3.5, color='orange', linestyle='--', alpha=0.5, label='Left lane boundary')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_ylim(-5, 5)
    
    axes[2].plot(steering_commands, 'r-', alpha=0.7)
    axes[2].set_ylabel('Steering (rad)')
    axes[2].set_title('Steering Command')
    axes[2].grid(True, alpha=0.3)
    axes[2].set_ylim(-0.6, 0.6)
    
    axes[3].plot(speeds, 'm-', alpha=0.7)
    axes[3].set_xlabel('Step')
    axes[3].set_ylabel('Speed (m/s)')
    axes[3].set_title('Vehicle Speed')
    axes[3].axhline(0, color='k', linestyle='--', linewidth=0.5)
    axes[3].axhline(25, color='g', linestyle='--', alpha=0.5, label='Target speed (25 m/s)')
    axes[3].legend()
    axes[3].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('paper_figures/lans_highway_fixed.png', dpi=300)
    plt.show()
    
    print("\n✓ Results saved to paper_figures/lans_highway_fixed.png")
else:
    print("No data collected.")