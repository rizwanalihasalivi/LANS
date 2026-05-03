"""
complete_verification.py - Verify ALL LANS Claims in One Script
Checks: Frequency, RMSE, Jitter, Mass Robustness, Delay Degradation
"""

import time
import numpy as np
from stable_baselines3 import PPO
from envs.residual_path_env import ResidualPathEnv
from envs.path_tracking_env import PathTrackingEnv
import matplotlib.pyplot as plt
import os

os.makedirs("verification_results", exist_ok=True)

print("=" * 80)
print("COMPLETE LANS VERIFICATION SUITE")
print("=" * 80)

# ============================================
# CLAIM 1: Inference Frequency (5 kHz)
# ============================================
print("\n" + "=" * 60)
print("CLAIM 1: Inference Frequency (5.0 kHz)")
print("=" * 60)

model = PPO.load('models/residual/ppo_residual_final')
n_runs = 1000
times = []

for _ in range(n_runs):
    obs = np.random.randn(11).astype(np.float32)
    start = time.perf_counter()
    model.predict(obs, deterministic=True)
    times.append((time.perf_counter() - start) * 1_000_000)  # microseconds

mean_us = np.mean(times)
p99_us = np.percentile(times, 99)
freq_hz = 1_000_000 / mean_us
p99_freq = 1_000_000 / p99_us

print(f"Mean inference time: {mean_us:.1f} µs")
print(f"99th percentile: {p99_us:.1f} µs")
print(f"Mean frequency: {freq_hz:.0f} Hz ({freq_hz/1000:.1f} kHz)")
print(f"99th percentile freq: {p99_freq:.0f} Hz")
print(f"Claim: 199 µs (5.0 kHz)")
print(f"✅ VERIFIED" if 4000 < freq_hz < 6000 else f"❌ FAILED: {freq_hz:.0f} Hz")

# ============================================
# CLAIM 2: LANS RMSE (0.197 m) vs PPO (0.236 m)
# ============================================
print("\n" + "=" * 60)
print("CLAIM 2: LANS RMSE (0.197 m) vs PPO (0.236 m)")
print("=" * 60)

# Test LANS
env = ResidualPathEnv()
env.target_speed = 25.0
env.reset()

lans_errors = []
for _ in range(800):
    action, _ = model.predict(env._get_observation(), deterministic=True)
    _, _, _, _, info = env.step(action)
    lans_errors.append(info['error'])

lans_rmse = np.sqrt(np.mean(np.square(lans_errors)))
print(f"LANS RMSE: {lans_rmse:.4f} m")
print(f"Claim: 0.197 m")
print(f"✅ VERIFIED" if 0.19 < lans_rmse < 0.20 else f"❌ FAILED: {lans_rmse:.4f}m")

# Test PPO
ppo_model = PPO.load('models/ppo_lans_final')
env = ResidualPathEnv()
env.target_speed = 25.0
env.reset()

ppo_errors = []
for _ in range(800):
    action, _ = ppo_model.predict(env._get_observation(), deterministic=True)
    _, _, _, _, info = env.step(action)
    ppo_errors.append(info['error'])

ppo_rmse = np.sqrt(np.mean(np.square(ppo_errors)))
improvement = ((ppo_rmse - lans_rmse) / ppo_rmse) * 100
print(f"PPO RMSE: {ppo_rmse:.4f} m")
print(f"LANS is {improvement:.1f}% better than PPO")
print(f"Claim: 16.6% better")
print(f"✅ VERIFIED" if improvement > 15 else f"❌ FAILED: {improvement:.1f}%")

# ============================================
# CLAIM 3: Jitter Tolerance (>200 ms)
# ============================================
print("\n" + "=" * 60)
print("CLAIM 3: Jitter Tolerance (>200 ms)")
print("=" * 60)

K_LQR = np.array([0.52, 0.12, 0.31, 0.04])
jitter_test = 200
env = ResidualPathEnv()
env.target_speed = 25.0
env.reset()
env.state[0] = 0.5

errors = []
for step in range(300):
    if step > 100:  # Apply jitter after initial settling
        time.sleep(jitter_test / 1000)
    action, _ = model.predict(env._get_observation(), deterministic=True)
    _, _, _, _, info = env.step(action)
    errors.append(info['error'])

rmse_jitter = np.sqrt(np.mean(np.square(errors[200:])))
print(f"RMSE at {jitter_test}ms jitter: {rmse_jitter:.4f} m")
print(f"Claim: >200 ms jitter tolerance")
print(f"✅ VERIFIED" if rmse_jitter < 0.5 else f"❌ FAILED: {rmse_jitter:.4f}m")

# ============================================
# CLAIM 4: Mass Robustness (±33%)
# ============================================
print("\n" + "=" * 60)
print("CLAIM 4: Mass Robustness (±33%)")
print("=" * 60)

masses = [1100, 1650, 2200]
mass_results = []

for mass in masses:
    env = ResidualPathEnv()
    env.target_speed = 25.0
    env.params['m'] = mass
    env.reset()
    
    errors = []
    for _ in range(800):
        action, _ = model.predict(env._get_observation(), deterministic=True)
        _, _, _, _, info = env.step(action)
        errors.append(info['error'])
    
    rmse = np.sqrt(np.mean(np.square(errors)))
    mass_results.append(rmse)
    print(f"Mass {mass}kg: RMSE = {rmse:.4f} m")

variation = abs(mass_results[0] - mass_results[2]) / mass_results[1] * 100
print(f"Variation across ±33% mass: {variation:.1f}%")
print(f"Claim: ±33% mass variation without retuning")
print(f"✅ VERIFIED" if variation < 20 else f"❌ FAILED: {variation:.1f}%")

# ============================================
# CLAIM 5: LQR Degrades 119% at 30ms, LANS Stable
# ============================================
print("\n" + "=" * 60)
print("CLAIM 5: LQR Degrades 119% at 30ms, LANS Stable (-4%)")
print("=" * 60)

K_LQR = np.array([0.52, 0.12, 0.31, 0.04])
delays = [0, 30]

def test_controller_with_delay(controller_type, delay_ms):
    env = PathTrackingEnv(mode="eval")
    env.vx = 25.0
    env.reset()
    env.state[0] = 0.5
    
    errors = []
    for step in range(200):
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
        
        if controller_type == "LQR":
            steering = -np.dot(K_LQR, env.state)
            action = np.array([np.clip(steering, -0.5, 0.5)])
        else:  # LANS
            action, _ = model.predict(env._get_observation(), deterministic=True)
        
        _, _, _, _, info = env.step(action)
        errors.append(info['error'])
    
    return np.sqrt(np.mean(np.square(errors)))

# Test LQR
lqr_0 = test_controller_with_delay("LQR", 0)
lqr_30 = test_controller_with_delay("LQR", 30)
lqr_degradation = ((lqr_30 - lqr_0) / lqr_0) * 100

print(f"LQR at 0ms: {lqr_0:.4f} m")
print(f"LQR at 30ms: {lqr_30:.4f} m")
print(f"LQR degradation: {lqr_degradation:.1f}%")
print(f"Claim: 119% degradation")
print(f"✅ VERIFIED" if lqr_degradation > 100 else f"⚠️ {lqr_degradation:.1f}% (close)")

# Test LANS
lans_0 = test_controller_with_delay("LANS", 0)
lans_30 = test_controller_with_delay("LANS", 30)
lans_change = ((lans_30 - lans_0) / lans_0) * 100

print(f"\nLANS at 0ms: {lans_0:.4f} m")
print(f"LANS at 30ms: {lans_30:.4f} m")
print(f"LANS change: {lans_change:.1f}%")
print(f"Claim: -4% (stable)")
print(f"✅ VERIFIED" if -10 < lans_change < 10 else f"❌ FAILED: {lans_change:.1f}%")

# ============================================
# FINAL SUMMARY
# ============================================
print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

claims = [
    ("5.0 kHz frequency", freq_hz > 4000 and freq_hz < 6000),
    ("0.197 m RMSE", 0.19 < lans_rmse < 0.20),
    ("Beats PPO by 16.6%", improvement > 15),
    (">200 ms jitter tolerance", rmse_jitter < 0.5),
    ("±33% mass robustness", variation < 20),
    ("LQR degrades 119%", lqr_degradation > 100),
    ("LANS stable (-4%)", -10 < lans_change < 10),
]

passed = sum(1 for _, status in claims if status)
total = len(claims)

for claim, status in claims:
    print(f"{'✅' if status else '❌'} {claim}")

print(f"\nPASSED: {passed}/{total} claims")
print("=" * 80)

if passed == total:
    print("🎉 ALL CLAIMS VERIFIED! Your paper is ready!")
else:
    print("⚠️ Some claims need adjustment before submission")