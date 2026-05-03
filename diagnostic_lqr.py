"""
diagnostic_lqr.py - Diagnose LQR gain calculation
"""

import sys
import os
sys.path.insert(0, os.getcwd())

import numpy as np
from scipy.linalg import solve_continuous_are
from models.bicycle_model import get_error_state_model, VEHICLE_PARAMS

print("="*60)
print("LQR GAIN DIAGNOSTIC")
print("="*60)

# Current parameters
print("\nCurrent Vehicle Parameters:")
print(f"  m  = {VEHICLE_PARAMS['m']} kg")
print(f"  Iz = {VEHICLE_PARAMS['Iz']} kg·m²")
print(f"  lf = {VEHICLE_PARAMS['lf']} m")
print(f"  lr = {VEHICLE_PARAMS['lr']} m")
print(f"  Cf = {VEHICLE_PARAMS['Cf']} N/rad")
print(f"  Cr = {VEHICLE_PARAMS['Cr']} N/rad")

# Calculate correct Iz
wheelbase = VEHICLE_PARAMS['lf'] + VEHICLE_PARAMS['lr']
correct_Iz = VEHICLE_PARAMS['m'] * (wheelbase**2) / 10
print(f"\nCalculated Iz = m * (lf+lr)² / 10 = {correct_Iz:.1f} kg·m²")
print(f"Paper Iz    = {VEHICLE_PARAMS['Iz']} kg·m²")

vx = 25.0
A, B = get_error_state_model(vx, VEHICLE_PARAMS)
B = B.reshape(-1, 1)

# LQR weights
Q = np.diag([100.0, 10.0, 50.0, 5.0])
R = np.array([[1.0]])

# Solve CARE
P = solve_continuous_are(A, B, Q, R)
K = np.linalg.solve(R, B.T @ P)
K = K.flatten()

print(f"\nCurrent LQR Gain:")
print(f"  K = [{K[0]:.3f}, {K[1]:.3f}, {K[2]:.3f}, {K[3]:.3f}]")
print(f"Expected: [0.520, 0.120, 0.310, 0.040]")

# Try with corrected Iz
print("\n" + "="*60)
print("TRYING WITH CORRECTED Iz")
print("="*60)

corrected_params = VEHICLE_PARAMS.copy()
corrected_params['Iz'] = correct_Iz

A2, B2 = get_error_state_model(vx, corrected_params)
B2 = B2.reshape(-1, 1)

P2 = solve_continuous_are(A2, B2, Q, R)
K2 = np.linalg.solve(R, B2.T @ P2)
K2 = K2.flatten()

print(f"Corrected Iz = {correct_Iz:.1f}")
print(f"K = [{K2[0]:.3f}, {K2[1]:.3f}, {K2[2]:.3f}, {K2[3]:.3f}]")

# Check if matches expected
expected = np.array([0.52, 0.12, 0.31, 0.04])
if np.allclose(K2, expected, atol=0.01):
    print("\n✅ MATCHES EXPECTED GAINS!")
else:
    print("\n⚠️ Still not matching. Check A and B matrices.")