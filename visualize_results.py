"""
plot_lqr_results.py - Visualize LQR Baseline Simulation Results
Plots lateral tracking performance and steering input
"""

import numpy as np
import matplotlib.pyplot as plt
import os
from scenarios.double_lane_change import double_lane_change

# ==========================================
# CONFIGURATION
# ==========================================
DT = 0.01  # 100 Hz
VX = 25.0  # 90 km/h

# Create output directory
os.makedirs("plots", exist_ok=True)


def load_lqr_results(filepath="lqr_run_results.npz"):
    """
    Load LQR simulation results from .npz file
    
    Expected keys:
        t: time array
        x: state array [vy, r, y, psi] or [e_y, e_y_dot, e_ψ, e_ψ_dot]
        u: control input (steering)
        y_ref: reference lateral position (optional)
    """
    if not os.path.exists(filepath):
        print(f"❌ Error: File {filepath} not found!")
        print("   Please run LQR simulation first to generate results.")
        return None
    
    data = np.load(filepath)
    print(f"✅ Loaded data from {filepath}")
    print(f"   Available keys: {list(data.keys())}")
    
    return data


def generate_reference_path(t, vx=VX):
    """
    Generate double lane change reference path
    """
    s = vx * t  # distance traveled
    y_ref = double_lane_change(s, vx=vx, lane_width=3.5)
    return y_ref


def compute_rmse(y_actual, y_ref):
    """
    Compute Root Mean Square Error
    """
    # Trim to same length
    min_len = min(len(y_actual), len(y_ref))
    return np.sqrt(np.mean((y_actual[:min_len] - y_ref[:min_len])**2))


def plot_lqr_results(data):
    """
    Plot LQR simulation results
    """
    
    # Extract data
    t = data['t']
    x = data['x']  # state array
    u = data['u']  # control input
    
    # Determine state order
    # Option 1: [vy, r, y, psi] (kinematic)
    # Option 2: [e_y, e_y_dot, e_ψ, e_ψ_dot] (error)
    
    if x.shape[1] == 4:
        # Try to identify which state is lateral position
        # Usually it's index 2 (y) or index 0 (e_y)
        if np.max(np.abs(x[:, 2])) > 5:  # Large values suggest absolute position
            lateral_pos = x[:, 2]
            state_type = "Absolute position [vy, r, y, psi]"
        else:
            # Small values suggest error state
            lateral_pos = x[:, 0]  # e_y
            state_type = "Error state [e_y, e_y_dot, e_ψ, e_ψ_dot]"
    else:
        lateral_pos = x[:, 0]  # fallback
        state_type = "Unknown state order"
    
    # Generate reference path
    y_ref = generate_reference_path(t, vx=VX)
    
    # Trim to same length
    min_len = min(len(lateral_pos), len(y_ref))
    t_trim = t[:min_len]
    lateral_trim = lateral_pos[:min_len]
    y_ref_trim = y_ref[:min_len]
    
    # Calculate RMSE
    rmse = compute_rmse(lateral_trim, y_ref_trim)
    
    print("\n" + "="*50)
    print("📊 LQR SIMULATION RESULTS")
    print("="*50)
    print(f"State interpretation: {state_type}")
    print(f"Simulation duration: {t[-1]:.2f} s")
    print(f"Number of steps: {len(t)}")
    print(f"RMSE: {rmse:.4f} m")
    print("="*50)
    
    # ==========================================
    # CREATE PLOT
    # ==========================================
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # ==========================================
    # TOP PLOT: Lateral Tracking
    # ==========================================
    ax1.plot(t_trim, y_ref_trim, 'k--', linewidth=2, label='Reference Path', alpha=0.8)
    ax1.plot(t_trim, lateral_trim, 'b-', linewidth=2, label='LQR Tracking')
    
    # Highlight transition zones
    s = VX * t_trim
    ax1.axvspan(20/VX, 45/VX, alpha=0.1, color='gray', label='Lane Change 1')
    ax1.axvspan(70/VX, 95/VX, alpha=0.1, color='gray', label='Lane Change 2')
    
    ax1.set_title(f'Vehicle Path Tracking - LQR Baseline (RMSE: {rmse:.4f}m)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Lateral Position [m]', fontsize=12)
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.set_xlim(0, t[-1])
    ax1.set_ylim(-0.5, 4.5)
    
    # ==========================================
    # BOTTOM PLOT: Steering Input
    # ==========================================
    ax2.plot(t, u, 'g-', linewidth=1.5, label='Steering Command')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax2.set_title('Control Input', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Steering Angle [rad]', fontsize=12)
    ax2.set_xlabel('Time [s]', fontsize=12)
    ax2.legend(loc='upper right', fontsize=10)
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.set_xlim(0, t[-1])
    ax2.set_ylim(-0.5, 0.5)
    
    # ==========================================
    # OPTIONAL: Error Plot
    # ==========================================
    fig2, ax3 = plt.subplots(1, 1, figsize=(12, 4))
    
    error = lateral_trim - y_ref_trim
    ax3.plot(t_trim, error, 'r-', linewidth=1.5, label='Tracking Error')
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax3.axhspan(-0.1, 0.1, alpha=0.2, color='green', label='±0.1m Target')
    ax3.set_xlabel('Time [s]', fontsize=12)
    ax3.set_ylabel('Lateral Error [m]', fontsize=12)
    ax3.set_title(f'Tracking Error (RMSE: {rmse:.4f}m)', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper right', fontsize=10)
    ax3.grid(True, linestyle='--', alpha=0.5)
    ax3.set_xlim(0, t[-1])
    ax3.set_ylim(-0.5, 0.5)
    
    plt.tight_layout()
    
    # Save figures
    plt.figure(fig.number)
    plt.savefig('plots/lqr_final_result.png', dpi=300, bbox_inches='tight')
    plt.savefig('plots/lqr_final_result.pdf', bbox_inches='tight')
    print("\n✅ Main plot saved to: plots/lqr_final_result.png")
    
    plt.figure(fig2.number)
    plt.savefig('plots/lqr_error_plot.png', dpi=300, bbox_inches='tight')
    print("✅ Error plot saved to: plots/lqr_error_plot.png")
    
    plt.show()


def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("📊 LQR SIMULATION VISUALIZATION")
    print("="*60)
    
    # Load data
    data = load_lqr_results("lqr_run_results.npz")
    
    if data is None:
        print("\n⚠️ No data available. Running sample LQR simulation...")
        
        # Create sample data for demonstration
        t = np.arange(0, 10, DT)
        y_ref = generate_reference_path(t)
        
        # Simulate LQR tracking with some error
        np.random.seed(42)
        lateral_pos = y_ref + 0.1 * np.sin(2 * np.pi * 0.2 * t) + 0.02 * np.random.randn(len(t))
        u = 0.2 * np.sin(2 * np.pi * 0.2 * t) + 0.1 * np.sin(2 * np.pi * 0.8 * t)
        
        # Create sample data
        data = {
            't': t,
            'x': np.column_stack([np.zeros_like(t), np.zeros_like(t), lateral_pos, np.zeros_like(t)]),
            'u': u
        }
        print("✅ Sample data created for demonstration")
    
    # Plot results
    plot_lqr_results(data)


if __name__ == "__main__":
    main()