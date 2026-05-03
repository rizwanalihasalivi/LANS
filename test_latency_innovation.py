"""
test_latency_innovation.py - Test LANS Controller Under Computational Jitter
Tests the full LANS architecture: δ_total = δ_LQR + β(τ)·δ_RL
"""

import numpy as np
import matplotlib.pyplot as plt
import time
import os
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv

# ==========================================
# CONFIGURATION
# ==========================================
SEED = 42
JITTER_START = 400  # steps (4 seconds at 100 Hz)
JITTER_END = 600    # steps (6 seconds at 100 Hz)
JITTER_DURATION_MS = 130  # milliseconds

# Set random seed
np.random.seed(SEED)

def run_latency_stress_test(with_lqr=True, with_adaptive_gain=True):
    """
    Run latency stress test with full LANS architecture
    
    Args:
        with_lqr (bool): Include LQR baseline
        with_adaptive_gain (bool): Include β(τ) modulation
    
    Returns:
        history_y: actual lateral positions
        history_ref: reference positions
        latencies: measured latencies
        betas: adaptive gain values (if applicable)
    """
    
    # ========== ENVIRONMENT SETUP ==========
    raw_env = PathTrackingEnv(mode="eval")
    raw_env.vx = 25.0  # 90 km/h
    raw_env.K_lqr = np.array([0.52, 0.12, 0.31, 0.04])  # LQR gains
    
    env = DummyVecEnv([lambda: raw_env])
    
    # Load normalization statistics
    norm_path = "models/vec_normalize_curriculum_final.pkl"
    if os.path.exists(norm_path):
        env = VecNormalize.load(norm_path, env)
        env.training = False
        env.norm_reward = False
        print(f"✅ Loaded normalization from {norm_path}")
    else:
        print(f"⚠️ Warning: {norm_path} not found. Using default normalization.")
    
    # Load model
    model_path = "models/ppo_curriculum_final"
    if os.path.exists(model_path + ".zip"):
        model = PPO.load(model_path)
        print(f"✅ Loaded model from {model_path}.zip")
    else:
        print(f"❌ Error: Model {model_path}.zip not found!")
        return None, None, None, None
    
    obs = env.reset()
    history_y = []
    history_ref = []
    latencies = []
    betas = []  # Track adaptive gain β(τ)
    
    print("🚀 Starting LANS Latency Stress Test...")
    print(f"   LQR Baseline: {'✓ Enabled' if with_lqr else '✗ Disabled'}")
    print(f"   Adaptive Gain β(τ): {'✓ Enabled' if with_adaptive_gain else '✗ Disabled'}")
    
    # ========== MAIN LOOP ==========
    for t_idx in range(len(raw_env.y_ref) - 1):
        
        # ========== STEP 1: MEASURE START TIME ==========
        t_start = time.perf_counter()
        
        # ========== STEP 2: SIMULATE JITTER ==========
        if JITTER_START < t_idx < JITTER_END:
            # Simulate 130ms jitter spike
            time.sleep(JITTER_DURATION_MS / 1000)
        
        # ========== STEP 3: GET STATE ==========
        # Current error state [e_y, e_y_dot, e_ψ, e_ψ_dot]
        current_state = raw_env.state if hasattr(raw_env, 'state') else np.zeros(4)
        
        # ========== STEP 4: LQR BASELINE ==========
        if with_lqr:
            δ_LQR = -np.dot(raw_env.K_lqr, current_state)
            δ_LQR = np.clip(δ_LQR, -0.5, 0.5)
        else:
            δ_LQR = 0.0
        
        # ========== STEP 5: PPO RESIDUAL ==========
        # PPO inference (this is what we measure latency for)
        action, _ = model.predict(obs, deterministic=True)
        δ_RL = action[0]
        
        # ========== STEP 6: ADAPTIVE GAIN β(τ) ==========
        # Compute current latency
        t_end = time.perf_counter()
        τ_current = (t_end - t_start) * 1000  # milliseconds
        
        if with_adaptive_gain:
            τ_th = 5.0      # ms
            τ_scale = 20.0  # ms
            if τ_current < τ_th:
                β = 1.0
            else:
                β = np.exp(-(τ_current - τ_th) / τ_scale)
        else:
            β = 1.0
        
        # ========== STEP 7: TOTAL STEERING COMMAND ==========
        δ_total = δ_LQR + β * δ_RL
        δ_total = np.clip(δ_total, -0.5, 0.5)
        
        # ========== STEP 8: APPLY CONTROL ==========
        # Override the action with our LANS command
        # Note: We need to pass the total steering to the environment
        # We'll modify the action in the step call
        obs, _, _, info = env.step(np.array([δ_total]))
        
        # ========== STEP 9: STORE DATA ==========
        history_y.append(info[0]["y_phys"])
        history_ref.append(raw_env.y_ref[raw_env.t_step])
        latencies.append(τ_current)
        betas.append(β)
        
        # Progress indicator
        if t_idx % 100 == 0:
            print(f"   Step {t_idx}/{len(raw_env.y_ref)-1}: τ={τ_current:.2f}ms, β={β:.3f}")
    
    print("\n✅ Test complete!")
    print(f"   Average latency: {np.mean(latencies):.2f} ms")
    print(f"   Max latency: {np.max(latencies):.2f} ms")
    print(f"   Min β: {np.min(betas):.3f}")
    
    return history_y, history_ref, latencies, betas


def plot_results(y, ref, lat, betas=None):
    """
    Plot latency stress test results
    
    Args:
        y: actual lateral positions
        ref: reference positions
        lat: measured latencies
        betas: adaptive gain values (optional)
    """
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # ==========================================
    # TOP PLOT: Trajectory Tracking
    # ==========================================
    ax1.plot(ref, 'r--', linewidth=1.5, label="Reference Path", alpha=0.7)
    ax1.plot(y, 'b-', linewidth=2, label="LANS Controller")
    
    # Highlight jitter region
    ax1.axvspan(JITTER_START, JITTER_END, alpha=0.2, color='red', label="Jitter Region (130ms)")
    
    ax1.set_xlabel('Time Step (0.01s)')
    ax1.set_ylabel('Lateral Position (m)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_title('LANS Controller: Stability Under 130ms Computational Jitter at 90 km/h')
    
    # ==========================================
    # BOTTOM PLOT: Latency and Adaptive Gain
    # ==========================================
    # Left y-axis: Latency
    ax2.plot(lat, 'g-', linewidth=1.5, label='Latency (ms)', alpha=0.7)
    ax2.set_xlabel('Time Step (0.01s)')
    ax2.set_ylabel('Latency (ms)', color='green')
    ax2.tick_params(axis='y', labelcolor='green')
    
    # Right y-axis: Adaptive gain β(τ)
    if betas is not None:
        ax2_twin = ax2.twinx()
        ax2_twin.plot(betas, 'orange', linewidth=2, label='β(τ)', alpha=0.8)
        ax2_twin.set_ylabel('β(τ) (Adaptive Gain)', color='orange')
        ax2_twin.tick_params(axis='y', labelcolor='orange')
        
        # Add horizontal line at β=1
        ax2_twin.axhline(y=1.0, color='orange', linestyle='--', alpha=0.5, linewidth=1)
    
    # Highlight jitter region
    ax2.axvspan(JITTER_START, JITTER_END, alpha=0.2, color='red', label="Jitter Region")
    
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # ==========================================
    # SAVE AND SHOW
    # ==========================================
    plt.tight_layout()
    plt.savefig("fresh_figures/fig_latency_innovation.png", dpi=300, bbox_inches='tight')
    plt.savefig("fresh_figures/fig_latency_innovation.pdf", bbox_inches='tight')
    
    print("\n✅ Plot saved to: fresh_figures/fig_latency_innovation.png")
    plt.show()


def run_comparison():
    """
    Run comparison: Pure PPO vs LANS with adaptive gain
    """
    print("\n" + "="*70)
    print("🔬 LATENCY STRESS TEST COMPARISON")
    print("="*70)
    
    # Test 1: Pure PPO (no LQR, no adaptive gain)
    print("\n" + "-"*50)
    print("TEST 1: Pure PPO (No LQR, β=1)")
    print("-"*50)
    y_ppo, ref_ppo, lat_ppo, _ = run_latency_stress_test(
        with_lqr=False, 
        with_adaptive_gain=False
    )
    
    # Test 2: LANS Full (LQR + adaptive gain)
    print("\n" + "-"*50)
    print("TEST 2: LANS Full (LQR + β(τ))")
    print("-"*50)
    y_lans, ref_lans, lat_lans, betas = run_latency_stress_test(
        with_lqr=True, 
        with_adaptive_gain=True
    )
    
    # Calculate RMSE
    rmse_ppo = np.sqrt(np.mean((np.array(y_ppo) - np.array(ref_ppo[:len(y_ppo)]))**2))
    rmse_lans = np.sqrt(np.mean((np.array(y_lans) - np.array(ref_lans[:len(y_lans)]))**2))
    
    print("\n" + "="*70)
    print("📊 RESULTS COMPARISON")
    print("="*70)
    print(f"Pure PPO RMSE: {rmse_ppo:.4f} m")
    print(f"LANS Full RMSE: {rmse_lans:.4f} m")
    print(f"Improvement: {(rmse_ppo - rmse_lans)/rmse_ppo*100:.1f}%")
    
    # Plot comparison
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Top: Trajectory comparison
    ax1.plot(ref_ppo, 'k--', linewidth=1.5, label="Reference", alpha=0.7)
    ax1.plot(y_ppo, 'r-', linewidth=1.5, label=f"Pure PPO (RMSE: {rmse_ppo:.3f}m)", alpha=0.8)
    ax1.plot(y_lans, 'g-', linewidth=2, label=f"LANS (RMSE: {rmse_lans:.3f}m)")
    ax1.axvspan(JITTER_START, JITTER_END, alpha=0.2, color='red', label="Jitter Region")
    ax1.set_ylabel('Lateral Position (m)')
    ax1.set_title('Comparison: Pure PPO vs LANS Under 130ms Jitter')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Bottom: Adaptive gain
    ax2.plot(betas, 'orange', linewidth=2, label='β(τ)')
    ax2.axvspan(JITTER_START, JITTER_END, alpha=0.2, color='red')
    ax2.set_xlabel('Time Step (0.01s)')
    ax2.set_ylabel('β(τ) (Adaptive Gain)')
    ax2.set_title('Adaptive Gain β(τ) During Jitter')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("fresh_figures/fig_latency_comparison.png", dpi=300, bbox_inches='tight')
    plt.show()
    
    return rmse_ppo, rmse_lans


# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    import os
    os.makedirs("fresh_figures", exist_ok=True)
    
    print("\n" + "="*70)
    print("🚀 LANS CONTROLLER: LATENCY INNOVATION TEST")
    print("="*70)
    
    # Run full comparison (recommended)
    rmse_ppo, rmse_lans = run_comparison()
    
    # Or run single test with plotting
    # y, ref, lat, betas = run_latency_stress_test(with_lqr=True, with_adaptive_gain=True)
    # plot_results(y, ref, lat, betas)