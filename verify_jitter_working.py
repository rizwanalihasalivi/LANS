"""
verify_jitter_working.py - Uses your working environment
"""

import time
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv
import os

# LQR gains
K_LQR = np.array([0.52, 0.12, 0.31, 0.04])

def adaptive_gain(tau_ms):
    """β(τ) from your paper"""
    if tau_ms < 5:
        return 1.0
    else:
        return np.exp(-(tau_ms - 5) / 20)

def lqr_control(error_state):
    return -np.dot(K_LQR, error_state)

print("=" * 60)
print("LANS JITTER TOLERANCE VERIFICATION")
print("=" * 60)

# Load model
print("Loading model...")
model = PPO.load('models/ppo_lans_final')
print("✅ Model loaded")

# Setup environment (same as your working benchmark)
raw_env = PathTrackingEnv(mode='eval')
raw_env.vx = 25.0
raw_env.K_lqr = K_LQR

env = DummyVecEnv([lambda: raw_env])

# Load normalization if exists
norm_path = "models/vec_normalize_lans_final.pkl"
if os.path.exists(norm_path):
    env = VecNormalize.load(norm_path, env)
    env.training = False
    env.norm_reward = False
    print("✅ Normalization loaded")

obs = env.reset()

# Test with different jitter levels
jitter_levels = [0, 50, 80, 100, 120, 130, 150, 180, 200]
results = []

for jitter_ms in jitter_levels:
    print(f"\n📊 Testing jitter: {jitter_ms} ms")
    
    # Reset environment
    obs = env.reset()
    errors = []
    latencies = []
    step_count = 0
    max_steps = len(raw_env.y_ref) - 1
    
    # Reset raw_env state
    raw_env.reset()
    
    for step in range(max_steps):
        # Get current error state
        current_state = raw_env.state if hasattr(raw_env, 'state') else np.zeros(4)
        
        # LQR baseline
        delta_lqr = lqr_control(current_state)
        delta_lqr = np.clip(delta_lqr, -0.5, 0.5)
        
        # PPO inference
        start = time.perf_counter()
        action, _ = model.predict(obs, deterministic=True)
        delta_rl = action[0]
        inference_time = (time.perf_counter() - start) * 1000  # ms
        
        # Simulate jitter delay
        if jitter_ms > 0:
            time.sleep(jitter_ms / 1000)
        
        # Adaptive gain
        total_latency = inference_time + jitter_ms
        beta = adaptive_gain(total_latency)
        
        # Total steering
        delta_total = delta_lqr + beta * delta_rl
        delta_total = np.clip(delta_total, -0.5, 0.5)
        
        # Apply control
        obs, _, _, info = env.step(np.array([delta_total]))
        
        # Get error
        if isinstance(info, list) and len(info) > 0:
            error = info[0].get('error', 0)
        elif isinstance(info, dict):
            error = info.get('error', 0)
        else:
            error = abs(current_state[0])
        
        errors.append(error)
        latencies.append(total_latency)
        step_count += 1
        
        if step % 100 == 0:
            print(f"   Step {step}: error={error:.4f}m, latency={total_latency:.1f}ms, beta={beta:.3f}")
    
    # Calculate metrics
    if errors:
        rmse = np.sqrt(np.mean(np.square(errors)))
        max_error = np.max(np.abs(errors))
        mean_latency = np.mean(latencies)
    else:
        rmse = 999
        max_error = 999
        mean_latency = 0
    
    is_stable = rmse < 1.0
    
    results.append({
        'jitter_ms': jitter_ms,
        'rmse': float(rmse),
        'max_error': float(max_error),
        'mean_latency': float(mean_latency),
        'stable': is_stable
    })
    
    status = "✅ STABLE" if is_stable else "❌ DIVERGED"
    print(f"   Steps: {step_count} | RMSE: {rmse:.4f}m | Max error: {max_error:.4f}m | {status}")

# Print summary
print("\n" + "=" * 60)
print("JITTER TOLERANCE SUMMARY")
print("=" * 60)
print(f"{'Jitter (ms)':<12} {'RMSE (m)':<12} {'Max Error (m)':<15} {'Status':<10}")
print("-" * 52)
for r in results:
    status = "STABLE" if r['stable'] else "DIVERGED"
    print(f"{r['jitter_ms']:<12} {r['rmse']:<12.4f} {r['max_error']:<15.4f} {status:<10}")

# Find critical threshold
critical = ">200"
for r in results:
    if not r['stable'] and r['jitter_ms'] < 200:
        critical = r['jitter_ms']
        break

print(f"\n🎯 Critical jitter threshold: {critical} ms")
print("   (RMSE exceeds 1m beyond this point)")

# Save results
import json
with open('jitter_test_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\n✅ Results saved to jitter_test_results.json")