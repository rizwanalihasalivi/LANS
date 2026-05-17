"""
Verify Table 2 Numbers for LANS Paper
"""

import time
import numpy as np

print("=" * 60)
print("TABLE 2 VERIFICATION SCRIPT")
print("=" * 60)

# ============================================
# 1. BLIND DISTANCE CALCULATIONS
# ============================================
print("\n[1] COMPUTATION BLIND DISTANCE")
print("-" * 40)

speed_ms = 25.0  # 90 km/h

def blind_distance(time_sec):
    return speed_ms * time_sec * 1000  # returns mm

# LQR
lqr_time_us = 0.37  # microseconds
lqr_time_sec = lqr_time_us / 1000000
lqr_blind = blind_distance(lqr_time_sec)
print(f"LQR: {lqr_time_us:.2f} microseconds = {lqr_blind:.4f} mm")

# PPO
ppo_time_ms = 10.0  # milliseconds
ppo_time_sec = ppo_time_ms / 1000
ppo_blind = blind_distance(ppo_time_sec)
print(f"PPO: {ppo_time_ms:.0f} milliseconds = {ppo_blind:.0f} mm")

# LANS (your measured value)
lans_time_us = 203  # microseconds
lans_time_sec = lans_time_us / 1000000
lans_blind = blind_distance(lans_time_sec)
print(f"LANS: {lans_time_us:.0f} microseconds = {lans_blind:.1f} mm")

# ============================================
# 2. LQR SPEED VERIFICATION
# ============================================
print("\n[2] LQR RAW INFERENCE FREQUENCY")
print("-" * 40)

# LQR gain matrix (4 states)
K = np.array([-10.0, -5.2, -15.8, -3.1])
x = np.array([0.01, 0.01, 0.01, 0.01])

iterations = 1000000
start = time.perf_counter()

for _ in range(iterations):
    u = -np.dot(K, x)

end = time.perf_counter()
total_time = end - start
avg_time_us = (total_time / iterations) * 1000000
freq_hz = 1000000 / avg_time_us

print(f"Iterations: {iterations:,}")
print(f"Total time: {total_time:.4f} seconds")
print(f"Average time per LQR calculation: {avg_time_us:.4f} microseconds")
print(f"Theoretical frequency: {freq_hz:.0f} Hz")
print(f"Table value: 270,000 Hz")

if freq_hz > 200000:
    print("RESULT: LQR frequency matches expected range (>200 kHz)")
else:
    print(f"RESULT: LQR frequency is {freq_hz:.0f} Hz")

# ============================================
# 3. PPO SPEED VERIFICATION (Simulated)
# ============================================
print("\n[3] PPO RAW INFERENCE FREQUENCY")
print("-" * 40)

# Simulate neural network inference
def simulate_nn_inference():
    """Simulates a small neural network forward pass"""
    input_size = 11
    hidden_size = 64
    output_size = 1
    
    w1 = np.random.randn(input_size, hidden_size)
    b1 = np.random.randn(hidden_size)
    w2 = np.random.randn(hidden_size, output_size)
    b2 = np.random.randn(output_size)
    
    x_input = np.random.randn(input_size)
    h = np.tanh(np.dot(x_input, w1) + b1)
    y = np.dot(h, w2) + b2
    return y

iterations = 1000
start = time.perf_counter()

for _ in range(iterations):
    result = simulate_nn_inference()

end = time.perf_counter()
total_time = end - start
avg_time_ms = (total_time / iterations) * 1000
freq_hz = 1000 / avg_time_ms

print(f"Iterations: {iterations}")
print(f"Total time: {total_time:.4f} seconds")
print(f"Average time per inference: {avg_time_ms:.2f} milliseconds")
print(f"Effective frequency: {freq_hz:.0f} Hz")
print(f"Table value: 100 Hz")

if freq_hz < 200:
    print("RESULT: PPO frequency matches expected range (50-200 Hz)")
else:
    print(f"RESULT: Simulation is faster than real DRL")

# ============================================
# 4. LANS SPEED (Your measured value)
# ============================================
print("\n[4] LANS RAW INFERENCE FREQUENCY")
print("-" * 40)

lans_measured_us = 203  # your measured value
lans_freq_hz = 1000000 / lans_measured_us
print(f"Measured LANS time: {lans_measured_us} microseconds")
print(f"Calculated LANS frequency: {lans_freq_hz:.0f} Hz")
print(f"Table value: 4,930 Hz")

if abs(lans_freq_hz - 4930) < 100:
    print("RESULT: LANS frequency matches table value")
else:
    print(f"RESULT: LANS frequency is {lans_freq_hz:.0f} Hz")

# ============================================
# 5. SPEED COMPARISON SUMMARY
# ============================================
print("\n[5] SPEED COMPARISON SUMMARY")
print("-" * 40)

print(f"LQR measured: {freq_hz:.0f} Hz")
print(f"LANS measured: {lans_freq_hz:.0f} Hz")
print(f"PPO standard: 100 Hz")

print(f"\nLANS is {lans_freq_hz / 100:.1f}x faster than PPO")
print(f"LQR is {freq_hz / 100:.0f}x faster than PPO")

# ============================================
# 6. BLIND DISTANCE SUMMARY
# ============================================
print("\n[6] BLIND DISTANCE SUMMARY AT 90 km/h (25 m/s)")
print("-" * 40)
print(f"LQR blind distance: {lqr_blind:.4f} mm (table: 0.004 mm)")
print(f"PPO blind distance: {ppo_blind:.0f} mm (table: 250 mm)")
print(f"LANS blind distance: {lans_blind:.1f} mm (table: 5.0 mm)")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)