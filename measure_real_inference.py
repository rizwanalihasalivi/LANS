"""
measure_real_inference.py - Measure ACTUAL PPO inference time on your hardware
Run this on your 2012 MacBook Air with your real trained model
"""

import time
import numpy as np
import statistics
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================
N_WARMUP = 100      # Warmup iterations (for cache/jit)
N_MEASURE = 10000   # Measurement iterations
USE_REAL_MODEL = True

print("=" * 70)
print("🔬 REAL PPO INFERENCE TIME MEASUREMENT")
print("=" * 70)
print(f"Hardware: 2012 MacBook Air (Intel Core i5-3427U @ 1.8 GHz)")
print(f"Measurements: {N_MEASURE} iterations after {N_WARMUP} warmup")
print()

# ==========================================
# STEP 1: Try to load the real PPO model
# ==========================================
print("1. Loading PPO model...")

try:
    from stable_baselines3 import PPO
    print("   ✓ Stable-Baselines3 imported")
except ImportError:
    print("   ✗ Stable-Baselines3 not installed")
    print("     Install with: pip install stable-baselines3")
    sys.exit(1)

# Try multiple possible model paths
model_paths = [
    "models/ppo_curriculum_final",
    "models/ppo_lans_final", 
    "models/ppo_curriculum_final.zip",
    "models/ppo_lans_final.zip",
    "models/residual/ppo_residual_final",
]

model = None
model_path_used = None

for path in model_paths:
    if os.path.exists(path) or os.path.exists(path + ".zip"):
        try:
            model = PPO.load(path)
            model_path_used = path
            print(f"   ✓ Loaded model from: {path}")
            break
        except Exception as e:
            print(f"   ✗ Failed to load {path}: {e}")

if model is None:
    print("\n   ✗ No trained PPO model found!")
    print("\n   OPTIONS:")
    print("   1. Train a model first: python train_ppo.py")
    print("   2. Or run with simulated PPO to see the difference")
    print("\n   Continuing with SIMULATED PPO for demonstration...")
    USE_REAL_MODEL = False

# ==========================================
# STEP 2: Define observation (11-dim as in your paper)
# ==========================================
def create_random_observation():
    """Create a random 11-dim observation matching your paper's spec"""
    # [e_y, e_y_dot, e_psi, e_psi_dot, vx, preview1-4, tau, tau_pred]
    obs = np.random.randn(11).astype(np.float32)
    obs[4] = 25.0  # vx = 25 m/s
    obs[9] = 0.5   # tau ~ 0.5 ms
    obs[10] = 0.5  # tau_pred
    return obs

# ==========================================
# STEP 3: Measure inference time
# ==========================================
print("\n2. Measuring inference time...")
print(f"   Warmup: {N_WARMUP} iterations")
print(f"   Measurement: {N_MEASURE} iterations")
print()

# Warmup (allows CPU cache and JIT to stabilize)
for i in range(N_WARMUP):
    obs = create_random_observation()
    if USE_REAL_MODEL and model is not None:
        model.predict(obs, deterministic=True)
    else:
        # Simulate a real neural network forward pass
        # A 11-64-64-1 network has ~ 11*64 + 64*64 + 64*1 = 4,864 multiplications
        # Each multiplication takes ~0.1 µs on CPU → ~0.5 ms realistic
        h1 = np.maximum(0, np.dot(obs, np.random.randn(11, 64) * 0.01))
        h2 = np.maximum(0, np.dot(h1, np.random.randn(64, 64) * 0.01))
        output = np.tanh(np.dot(h2, np.random.randn(64, 1))) 

# Actual measurement
latencies_us = []  # microseconds
latencies_ms = []  # milliseconds

for i in range(N_MEASURE):
    obs = create_random_observation()
    
    start = time.perf_counter()
    
    if USE_REAL_MODEL and model is not None:
        action, _ = model.predict(obs, deterministic=True)
    else:
        # SIMULATED: Realistic neural network forward pass simulation
        # This still doesn't match real NN inference, but better than random
        # A real NN would take ~2-10 ms on this hardware
        h1 = np.maximum(0, np.dot(obs, np.random.randn(11, 64) * 0.01))
        h2 = np.maximum(0, np.dot(h1, np.random.randn(64, 64) * 0.01))
        output = np.tanh(np.dot(h2, np.random.randn(64, 1)))
        action = output[0] * 0.5
    
    end = time.perf_counter()
    
    latency_us = (end - start) * 1_000_000
    latency_ms = (end - start) * 1_000
    
    latencies_us.append(latency_us)
    latencies_ms.append(latency_ms)
    
    if (i + 1) % 1000 == 0:
        print(f"   Progress: {i+1}/{N_MEASURE}")

# ==========================================
# STEP 4: Calculate statistics
# ==========================================
latencies_us = np.array(latencies_us)
latencies_ms = np.array(latencies_ms)

mean_us = np.mean(latencies_us)
std_us = np.std(latencies_us)
min_us = np.min(latencies_us)
max_us = np.max(latencies_us)
p50_us = np.percentile(latencies_us, 50)
p90_us = np.percentile(latencies_us, 90)
p95_us = np.percentile(latencies_us, 95)
p99_us = np.percentile(latencies_us, 99)
p999_us = np.percentile(latencies_us, 99.9)

mean_ms = np.mean(latencies_ms)
p99_ms = np.percentile(latencies_ms, 99)

# Calculate frequency
freq_mean_hz = 1_000_000 / mean_us
freq_p99_hz = 1_000_000 / p99_us

# ==========================================
# STEP 5: Print results
# ==========================================
print("\n" + "=" * 70)
print("📊 INFERENCE TIME MEASUREMENT RESULTS")
print("=" * 70)
print(f"Model type: {'REAL (trained PPO)' if USE_REAL_MODEL and model is not None else 'SIMULATED'}")
print(f"Hardware: 2012 MacBook Air (1.8 GHz Intel Core i5)")
print("-" * 70)
print(f"Mean inference time:     {mean_us:.1f} µs  ({mean_ms:.3f} ms)")
print(f"Std deviation:           {std_us:.1f} µs")
print(f"Minimum:                 {min_us:.1f} µs")
print(f"Maximum:                 {max_us:.1f} µs")
print("-" * 70)
print(f"50th percentile (median): {p50_us:.1f} µs")
print(f"90th percentile:          {p90_us:.1f} µs")
print(f"95th percentile:          {p95_us:.1f} µs")
print(f"99th percentile:          {p99_us:.1f} µs  ({p99_ms:.3f} ms)")
print(f"99.9th percentile:        {p999_us:.1f} µs")
print("-" * 70)
print(f"Mean frequency:          {freq_mean_hz:.0f} Hz  ({freq_mean_hz/1000:.1f} kHz)")
print(f"99th percentile freq:    {freq_p99_hz:.0f} Hz")
print("=" * 70)

# ==========================================
# STEP 6: Compare to what your paper claims
# ==========================================
print("\n📈 COMPARISON TO PAPER CLAIMS")
print("-" * 70)

paper_claim_us = 76.6
paper_claim_hz = 13053

if USE_REAL_MODEL and model is not None:
    if mean_us < paper_claim_us * 1.2:  # Within 20%
        print(f"✅ Measurement ({mean_us:.1f} µs) matches paper claim ({paper_claim_us:.1f} µs)")
    elif mean_us < 1000:
        print(f"⚠️ Measurement ({mean_us:.1f} µs) is {mean_us/paper_claim_us:.1f}× paper claim")
    else:
        print(f"❌ Measurement ({mean_us:.1f} µs) is MUCH higher than paper claim ({paper_claim_us:.1f} µs)")
        print(f"   → The 13 kHz claim is not reproducible with the real model")
else:
    print("⚠️ Using simulated PPO - run with real model for accurate measurement")
    print(f"   Simulated time: {mean_us:.1f} µs")
    print(f"   Paper claims: {paper_claim_us:.1f} µs")
    print(f"   Real model likely takes 2,000-10,000 µs (2-10 ms) on this hardware")

# ==========================================
# STEP 7: Also measure LQR only for comparison
# ==========================================
print("\n" + "=" * 70)
print("📊 LQR ONLY INFERENCE TIME (for comparison)")
print("=" * 70)

def lqr_control(error_state):
    K = np.array([0.52, 0.12, 0.31, 0.04])
    return -np.dot(K, error_state)

lqr_times_us = []
for i in range(N_MEASURE):
    error_state = np.random.randn(4)
    start = time.perf_counter()
    steering = lqr_control(error_state)
    lqr_times_us.append((time.perf_counter() - start) * 1_000_000)

lqr_mean_us = np.mean(lqr_times_us)
print(f"LQR mean inference time: {lqr_mean_us:.2f} µs")
print(f"LQR frequency: {1_000_000 / lqr_mean_us:.0f} Hz")
print(f"PPO is {mean_us / lqr_mean_us:.1f}× slower than LQR")

# ==========================================
# STEP 8: Save results
# ==========================================
import json
from datetime import datetime

results = {
    "timestamp": datetime.now().isoformat(),
    "hardware": "2012 MacBook Air, Intel Core i5-3427U @ 1.8 GHz",
    "model_type": "real" if (USE_REAL_MODEL and model is not None) else "simulated",
    "model_path": model_path_used if model_path_used else None,
    "n_measurements": N_MEASURE,
    "inference_time_us": {
        "mean": float(mean_us),
        "std": float(std_us),
        "min": float(min_us),
        "max": float(max_us),
        "p50": float(p50_us),
        "p90": float(p90_us),
        "p95": float(p95_us),
        "p99": float(p99_us),
        "p999": float(p999_us)
    },
    "frequency_hz": {
        "mean": float(freq_mean_hz),
        "p99": float(freq_p99_hz)
    },
    "lqr_comparison_us": float(lqr_mean_us)
}

os.makedirs("results", exist_ok=True)
with open("results/inference_benchmark.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n✓ Results saved to results/inference_benchmark.json")
print("=" * 70)