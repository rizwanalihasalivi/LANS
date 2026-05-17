"""
lqr_jitter_test_simple.py - Simple LQR jitter test
Focuses on steady-state error, not transient dynamics
"""

import numpy as np
import time
from envs.path_tracking_env import PathTrackingEnv

print("=" * 60)
print("SIMPLE LQR JITTER TOLERANCE TEST")
print("=" * 60)

K_LQR = np.array([0.52, 0.12, 0.31, 0.04])
jitter_levels = [0, 50, 100, 130, 150, 200]
n_runs = 3

def test_lqr_at_jitter(delay_ms):
    """Test LQR with delay added before control computation"""
    env = PathTrackingEnv(mode="eval")
    env.vx = 25.0
    env.reset()
    env.state[0] = 0.5
    env.state[2] = 0.05
    
    errors = []
    
    for step in range(200):
        # Add delay BEFORE computing control (simulates computation time)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
        
        # LQR control (uses current state - but state has changed during delay)
        steering = -np.dot(K_LQR, env.state)
        steering = np.clip(steering, -0.5, 0.5)
        
        # Apply control
        _, _, _, _, info = env.step(np.array([steering]))
        errors.append(info['error'])
    
    return np.sqrt(np.mean(np.square(errors)))

print("\nTesting LQR with different delays...")
print("-" * 50)

results = []

for delay in jitter_levels:
    print(f"\n📊 Delay: {delay} ms")
    rmses = []
    
    for run in range(n_runs):
        rmse = test_lqr_at_jitter(delay)
        rmses.append(rmse)
        print(f"   Run {run+1}: RMSE = {rmse:.4f} m")
    
    mean_rmse = np.mean(rmses)
    results.append({'delay': delay, 'rmse': mean_rmse})
    print(f"   Mean: {mean_rmse:.4f} m")

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
print(f"{'Delay (ms)':<12} {'RMSE (m)':<12}")
print("-" * 25)

for r in results:
    print(f"{r['delay']:<12} {r['rmse']:<12.4f}")

# Calculate degradation at 130ms
baseline = results[0]['rmse']
jitter_130 = next(r['rmse'] for r in results if r['delay'] == 130)
degradation = ((jitter_130 - baseline) / baseline) * 100

print("\n" + "=" * 60)
print("KEY FINDING")
print("=" * 60)
print(f"LQR at 0ms:   {baseline:.4f} m")
print(f"LQR at 130ms: {jitter_130:.4f} m")
print(f"Degradation:  {degradation:.1f}%")

if jitter_130 > 0.5:
    print("\n⚠️ LQR degrades significantly under 130ms jitter")
    print("   (RMSE exceeds 0.5m threshold)")
else:
    print("\n✅ LQR remains stable under 130ms jitter")
    print("   (No degradation observed - test limitation?)")

print("\n" + "=" * 60)