"""
double_lane_change.py - ISO 3888-2 Reference Path with Curvature
Implements Equations (2)-(4) and (62)-(66) from paper
"""

import numpy as np

def double_lane_change(s, lane_width=3.5):
    """
    Generate ISO 3888-2 double lane change reference.
    
    Args:
        s: longitudinal distance (m)
        lane_width: lane width in meters (default 3.5)
    
    Returns:
        y_ref: lateral position (m)
    """
    y_ref = np.zeros_like(s)
    
    # First lane change (20m to 45m) - Equation (63)
    mask1 = (s >= 20) & (s < 45)
    if np.any(mask1):
        t = (s[mask1] - 20) / 25
        y_ref[mask1] = (lane_width / 2) * (1 - np.cos(np.pi * t))
    
    # Maintain left lane (45m to 70m)
    mask2 = (s >= 45) & (s < 70)
    if np.any(mask2):
        y_ref[mask2] = lane_width
    
    # Return to original lane (70m to 95m) - Equation (65)
    mask3 = (s >= 70) & (s < 95)
    if np.any(mask3):
        t = (s[mask3] - 70) / 25
        y_ref[mask3] = lane_width - (lane_width / 2) * (1 - np.cos(np.pi * t))
    
    return y_ref


def double_lane_change_with_derivatives(s, lane_width=3.5):
    """
    Generate reference with first and second derivatives for curvature.
    
    Returns:
        y_ref, y_prime, y_dprime
    """
    y_ref = np.zeros_like(s)
    y_prime = np.zeros_like(s)
    y_dprime = np.zeros_like(s)
    
    # First lane change (20m to 45m) - Equations (63)-(64)
    mask1 = (s >= 20) & (s < 45)
    if np.any(mask1):
        t = (s[mask1] - 20) / 25
        y_ref[mask1] = (lane_width / 2) * (1 - np.cos(np.pi * t))
        y_prime[mask1] = (lane_width * np.pi / 50) * np.sin(np.pi * t)
        y_dprime[mask1] = (lane_width * np.pi**2 / 1250) * np.cos(np.pi * t)
    
    # Maintain left lane (45m to 70m)
    mask2 = (s >= 45) & (s < 70)
    if np.any(mask2):
        y_ref[mask2] = lane_width
        y_prime[mask2] = 0
        y_dprime[mask2] = 0
    
    # Return to original lane (70m to 95m) - Equations (65)-(66)
    mask3 = (s >= 70) & (s < 95)
    if np.any(mask3):
        t = (s[mask3] - 70) / 25
        y_ref[mask3] = lane_width - (lane_width / 2) * (1 - np.cos(np.pi * t))
        y_prime[mask3] = -(lane_width * np.pi / 50) * np.sin(np.pi * t)
        y_dprime[mask3] = -(lane_width * np.pi**2 / 1250) * np.cos(np.pi * t)
    
    return y_ref, y_prime, y_dprime


def compute_curvature(y_prime, y_dprime):
    """
    Compute path curvature - Equation (4) and (62)
    
    κ(s) = y''(s) / (1 + y'(s)²)^(3/2)
    """
    return y_dprime / (1 + y_prime**2)**(1.5)


def compute_reference_heading(y_prime):
    """
    Compute reference heading angle - Equation (3)
    
    ψ_ref = arctan(dy/dx)
    """
    return np.arctan2(y_prime, 1.0)


def generate_reference_path(vx=25.0, duration=10.0, dt=0.01):
    """
    Generate complete reference path for simulation.
    
    Returns:
        t: time array
        s: distance array
        y_ref: lateral position
        psi_ref: heading angle (rad)
        kappa: curvature (1/m)
    """
    t = np.arange(0, duration, dt)
    s = vx * t
    
    y_ref, y_prime, y_dprime = double_lane_change_with_derivatives(s)
    psi_ref = compute_reference_heading(y_prime)
    kappa = compute_curvature(y_prime, y_dprime)
    
    return t, s, y_ref, psi_ref, kappa


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    
    print("="*60)
    print("Double Lane Change Reference Path Verification")
    print("="*60)
    
    vx = 25.0  # 90 km/h
    t, s, y_ref, psi_ref, kappa = generate_reference_path(vx=vx, duration=10.0)
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 8))
    
    # Plot 1: Lateral position
    axes[0].plot(s, y_ref, 'b-', linewidth=2)
    axes[0].axvspan(20, 45, alpha=0.2, color='green', label='Lane Change 1')
    axes[0].axvspan(70, 95, alpha=0.2, color='orange', label='Lane Change 2')
    axes[0].set_ylabel('Lateral Position (m)')
    axes[0].set_title(f'ISO 3888-2 Double Lane Change at {vx*3.6:.0f} km/h')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: Heading angle
    axes[1].plot(s, psi_ref * 180/np.pi, 'r-', linewidth=2)
    axes[1].set_ylabel('Heading ψ_ref (deg)')
    axes[1].grid(True, alpha=0.3)
    
    # Plot 3: Curvature
    axes[2].plot(s, kappa, 'g-', linewidth=2)
    axes[2].set_xlabel('Distance (m)')
    axes[2].set_ylabel('Curvature κ (1/m)')
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('double_lane_change_reference.png', dpi=150)
    plt.show()
    
    print(f"\n✅ Reference path generated:")
    print(f"   Length: {s[-1]:.0f} m")
    print(f"   Duration: {t[-1]:.1f} s")
    print(f"   Speed: {vx} m/s ({vx*3.6:.0f} km/h)")
    print(f"   Max curvature: {np.max(np.abs(kappa)):.4f} 1/m")
    print(f"   Max heading: {np.max(np.abs(psi_ref))*180/np.pi:.1f} deg")
