import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# Ensure modules are discoverable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.bicycle_model import bicycle_model
from controllers.lqr_controller import lqr_gain
from scenarios.double_lane_change import double_lane_change

# =================================================================
# 1. Configuration & Physics Setup
# =================================================================
dt, T, vx = 0.01, 8.0, 15.0
t = np.arange(0, T, dt)
dist = vx * t 

params = {
    "m": 1500.0, "Iz": 3000.0, 
    "lf": 1.2, "lr": 1.6, 
    "Cf": 80000.0, "Cr": 80000.0
}

# =================================================================
# 2. Ultra-High Precision Tuning
# =================================================================
A, B = bicycle_model(vx, params)

# Q = [lateral_velocity, yaw_rate, lateral_position, heading_error]
# Pushed y-weight to 650 to force the error below 0.2m
Q = np.diag([1.0, 1.0, 650.0, 35.0]) 
R = np.array([[45.0]]) # Balanced damping for smooth steering

K = lqr_gain(A, B, Q, R)

# =================================================================
# 3. Path Generation & Simulation Loop
# =================================================================
y_ref = double_lane_change(t, vx=vx, lane_width=3.5)

x = np.zeros((4, len(t))) 
steering = []

# PREVIEW LOGIC: Look 0.35 seconds ahead to compensate for vehicle lag
lookahead_time = 0.35 
look_idx = int(lookahead_time / dt)

for i in range(len(t)-1):
    e = x[:, i].copy()
    e[2] = x[2, i] - y_ref[i]
    
    # 1. Feedback Control (LQR)
    u_fb = float(-K @ e)
    
    # 2. Advanced Preview Feedforward
    # Anticipates curvature peaks to prevent 'clipping'
    if i + look_idx < len(y_ref):
        future_target = y_ref[i + look_idx]
        u_ff = (future_target - y_ref[i]) * 1.12 # Anticipation Gain
    else:
        u_ff = 0
        
    u_total = np.clip(u_fb + u_ff, -0.6, 0.6)
    steering.append(u_total)
    
    # State Update
    dx = A @ x[:, i] + B.flatten() * u_total
    x[:, i+1] = x[:, i] + dt * dx

# =================================================================
# 4. Professional Analysis & Visualization
# =================================================================
error = x[2, :] - y_ref
rmse = np.sqrt(np.mean(error**2))
max_e = np.max(np.abs(error))

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

# Panel 1: Trajectory
ax1.plot(dist, y_ref, 'r--', label='Reference Path', alpha=0.7)
ax1.plot(dist, x[2, :], 'b-', label='Ultra-LQR (Final)', linewidth=2)
ax1.set_ylabel('Lateral Pos [m]')
ax1.set_title(f'Step 1 Finalized: Ultra-Precision Baseline\nMax Error: {max_e:.4f}m | RMSE: {rmse:.4f}m', fontweight='bold')
ax1.legend(loc='upper right')

# Panel 2: Tracking Error (Fixed Scale for Professional Comparison)
ax2.plot(dist, error, 'r-', linewidth=1.5)
ax2.axhline(0, color='black', lw=1, alpha=0.5)
ax2.set_ylabel('Lateral Error [m]')
ax2.set_ylim([-0.3, 0.3]) # Ensures we see the full peak without clipping
ax2.grid(True, linestyle='--', alpha=0.4)

# Panel 3: Steering Angle
ax3.plot(dist[:-1], steering, 'g-', linewidth=1.5)
ax3.set_ylabel('Steering [rad]')
ax3.set_xlabel('Longitudinal Distance [m]')

for ax in [ax1, ax2, ax3]:
    ax.grid(True, linestyle='--', alpha=0.4)

plt.tight_layout()

# Export Data for PPO Step 2
os.makedirs('results', exist_ok=True)
df = pd.DataFrame({'dist': dist, 'ref': y_ref, 'actual': x[2,:], 'error': error})
df.to_csv('results/lqr_ultra_precision_baseline.csv', index=False)

plt.show()

print(f"ULTRA-PRECISION BASELINE LOCKED.\nMax Error: {max_e:.4f}m\nRMSE: {rmse:.4f}m")