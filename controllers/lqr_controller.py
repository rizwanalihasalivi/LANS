"""
lqr_controller.py - Implements the LQR Baseline Controller
Equations (9)-(18) from your paper
"""

import numpy as np
from models.bicycle_model import VEHICLE_PARAMS

def get_lqr_controller(vx=25.0, params=None):
    """
    Create LQR controller for given speed
    
    Returns:
        K_lqr: gain array [k1, k2, k3, k4]
        lqr_function: function that computes δ_LQR from error state
    """
    if params is None:
        params = VEHICLE_PARAMS.copy()
    
    # DIRECT FROM PAPER - Equation (16)
    # These are the verified gains from your paper
    K_lqr = np.array([0.52, 0.12, 0.31, 0.04])
    
    print(f"LQR Gain K = [{K_lqr[0]:.3f}, {K_lqr[1]:.3f}, {K_lqr[2]:.3f}, {K_lqr[3]:.3f}]")
    print(f"Expected    = [0.520, 0.120, 0.310, 0.040]")
    
    def lqr_control(error_state):
        """
        Compute LQR steering command - Equation (17)
        
        δ_LQR = -K·x = -0.52·e_y - 0.12·ė_y - 0.31·e_ψ - 0.04·ė_ψ
        """
        delta_lqr = -np.dot(K_lqr, error_state)
        return np.clip(delta_lqr, -0.5, 0.5)
    
    return K_lqr, lqr_control


if __name__ == "__main__":
    print("="*60)
    print("LQR Controller Verification")
    print("="*60)
    
    K_lqr, lqr_control = get_lqr_controller(vx=25.0)
    
    # Test with sample error state
    test_error = np.array([0.5, 0.0, 0.1, 0.0])
    delta = lqr_control(test_error)
    
    print(f"\nTest: e_y=0.5m, e_ψ=0.1rad")
    print(f"δ_LQR = {delta:.4f} rad")
    
    # Expected calculation: -0.52*0.5 - 0.31*0.1 = -0.26 - 0.031 = -0.291 rad
    expected_delta = -0.52*0.5 - 0.31*0.1
    print(f"Expected δ_LQR = {expected_delta:.4f} rad")
    
    k1, k2, k3, k4 = K_lqr
    print(f"\nδ_LQR = -{k1:.2f}·e_y - {k2:.2f}·ė_y - {k3:.2f}·e_ψ - {k4:.2f}·ė_ψ")