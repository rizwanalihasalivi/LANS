"""
bicycle_model.py - Implements the Error State Model from your diagram
Equations (40)-(52) from your paper
State: x = [e_y, ė_y, e_ψ, ė_ψ]ᵀ
"""

import numpy as np
from scipy.linalg import expm

def get_error_state_model(vx, params):
    """
    Returns the continuous-time error state matrices A and B.
    """
    m = params["m"]
    Iz = params["Iz"]
    lf = params["lf"]
    lr = params["lr"]
    Cf = params["Cf"]
    Cr = params["Cr"]
    
    if vx < 0.1:
        vx = 0.1
    
    # A matrix - Equation (51) from paper
    A = np.array([
        [0, 1, 0, 0],
        [0, -(Cf + Cr) / (m * vx), (Cf + Cr) / m, (lr * Cr - lf * Cf) / (m * vx)],
        [0, 0, 0, 1],
        [0, (lr * Cr - lf * Cf) / (Iz * vx), (lf * Cf - lr * Cr) / Iz, -(lf**2 * Cf + lr**2 * Cr) / (Iz * vx)]
    ], dtype=np.float64)
    
    # B matrix - Equation (52) from paper
    B = np.array([
        [0],
        [Cf / m],
        [0],
        [lf * Cf / Iz]
    ], dtype=np.float64)
    
    return A, B


# ==========================================
# ADD THIS FUNCTION - FIXES THE IMPORT ERROR
# ==========================================
def bicycle_model(vx, params):
    """
    Wrapper function that returns A and B matrices.
    This matches what path_tracking_env.py expects.
    
    Args:
        vx: longitudinal velocity (m/s)
        params: vehicle parameters dict
    
    Returns:
        A: 4x4 state matrix, B: 4x1 input matrix (flattened)
    """
    A, B = get_error_state_model(vx, params)
    return A, B.flatten()  # Return B as flattened array (4,)


def discretize_error_state_model(A, B, dt):
    """
    Discretize the error state model - Equations (53)-(55)
    """
    n = A.shape[0]
    M = np.zeros((n + 1, n + 1))
    M[:n, :n] = A * dt
    M[:n, n] = B.flatten() * dt
    # Zero lower block is required for the zero-order-hold exponential.
    
    M_exp = expm(M)
    A_d = M_exp[:n, :n]
    B_d = M_exp[:n, n:n+1]
    
    return A_d, B_d


def get_error_state_from_measurements(y_actual, y_ref, psi_actual, psi_ref, vx, vy, r, kappa):
    """
    Convert raw measurements to error state - Equation (6)
    
    Returns:
        x = [e_y, ė_y, e_ψ, ė_ψ]ᵀ
    """
    e_y = y_actual - y_ref                    # Lateral error
    e_psi = psi_actual - psi_ref              # Heading error
    e_y_dot = vy + vx * e_psi                 # Lateral error rate - Equation (41)
    e_psi_dot = r - kappa * vx                # Yaw rate error - Equation (42)
    
    return np.array([e_y, e_y_dot, e_psi, e_psi_dot])


# Vehicle parameters - Table 2 from paper
VEHICLE_PARAMS = {
    "m": 1650.0,      # kg
    "Iz": 4224.0,     # kg·m²
    "lf": 1.2,        # m
    "lr": 1.4,        # m
    "Cf": 80000.0,    # N/rad
    "Cr": 80000.0     # N/rad
}

if __name__ == "__main__":
    print("="*60)
    print("Error State Model Verification")
    print("="*60)
    
    vx = 25.0  # 90 km/h
    A, B = get_error_state_model(vx, VEHICLE_PARAMS)
    
    print(f"\nA matrix (4x4):\n{A}")
    print(f"\nB matrix (4x1):\n{B}")
    
    # Verify eigenvalues (should be stable)
    eigvals = np.linalg.eigvals(A)
    print(f"\nEigenvalues: {eigvals}")
    if np.all(np.real(eigvals) < 0):
        print("✅ System is open-loop stable")
    else:
        print("⚠️ System has unstable modes")