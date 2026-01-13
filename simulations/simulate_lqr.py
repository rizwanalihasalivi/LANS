import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from models.bicycle_model import bicycle_model
from controllers.lqr_controller import lqr_gain
from scenarios.double_lane_change import double_lane_change

# ====================
# Simulation Setup
# ====================
dt = 0.01               # Time step (s)
T = 10.0                # Total time (s) — longer for settling
t = np.arange(0, T, dt)

# Vehicle parameters
params = {
    "m": 1500.0,
    "Iz": 3000.0,
    "lf": 1.2,
    "lr": 1.6,
    "Cf": 80000.0,
    "Cr": 80000.0
}

vx = 15.0  # Constant speed (m/s)

# ====================
# System Matrices & LQR Gain
# ====================
A, B = bicycle_model(vx, params)

# Tuned Q and R (softer for smooth tracking, reduced oscillations)
Q = np.diag([10.0, 10.0, 5.0, 5.0])   # Balanced penalties
R = np.array([[20.0]])                 # Higher steering penalty

K = lqr_gain(A, B)  # Uses updated function

# ====================
# Smooth Reference Path (Sine-based double lane change)
# ====================
y_ref = double_lane_change(t, vx=vx, lane_width=3.5)

# ====================
# Initial State
# ====================
x = np.zeros((4, len(t)))  # [vy, r, y, psi]

# Optional initial offset to test tracking
x[2, 0] = 0.5  # Start 0.5 m off

# ====================
# Simulation Loop
# ====================
steering = []  # Collect steering for plotting

for i in range(len(t)-1):
    # 1. Tracking error (lateral position only)
    e = x[:, i].copy()
    e[2] = x[2, i] - y_ref[i]  # e_y = y - y_ref

    # 2. LQR control
    u = float(-K @ e)
    u = np.clip(u, -0.4, 0.4)  # Steering limit ±23 deg

    steering.append(u)

    # 3. Update state (Euler)
    dx = A @ x[:, i] + B.flatten() * u
    x[:, i+1] = x[:, i] + dt * dx

# ====================
# Results Plots
# ====================
fig, axs = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

# 1. Trajectory
x_pos = vx * t  # Distance along road
axs[0].plot(x_pos, x[2, :], label='Vehicle Path', color='blue', linewidth=2)
axs[0].plot(x_pos, y_ref, '--', label='Reference Path', color='orange', linewidth=2)
axs[0].set_ylabel('Lateral Position (m)')
axs[0].set_title('Trajectory Comparison')
axs[0].legend()
axs[0].grid(True)

# 2. Lateral Error
axs[1].plot(t, x[2, :] - y_ref, color='red', linewidth=2)
axs[1].set_ylabel('Lateral Error (m)')
axs[1].set_title('Tracking Error')
axs[1].grid(True)
axs[1].axhline(0, color='black', linestyle='--', alpha=0.5)

# 3. Steering Angle
axs[2].plot(t[:-1], steering, color='green', linewidth=2)
axs[2].set_xlabel('Time (s)')
axs[2].set_ylabel('Steering Angle (rad)')
axs[2].set_title('Steering Input')
axs[2].grid(True)
axs[2].axhline(0, color='black', linestyle='--', alpha=0.5)

plt.suptitle('LQR Baseline Path Tracking - Double Lane Change', fontsize=16)
plt.tight_layout()
plt.show()

# Print final stats
final_error = np.abs(x[2, -1] - y_ref[-1])
print(f"Final lateral error: {final_error:.4f} m")
print(f"Max lateral error: {np.max(np.abs(x[2, :] - y_ref)):.4f} m")