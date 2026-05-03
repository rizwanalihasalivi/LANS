from stable_baselines3 import PPO
from envs.residual_path_env import ResidualPathEnv
import numpy as np
import time

print("=" * 70)
print("COMPLETE FAIR COMPARISON TEST")
print("=" * 70)

# LQR gains
K_LQR = np.array([0.52, 0.12, 0.31, 0.04])

# Test parameters
INITIAL_ERROR = 0.5  # meters
INITIAL_HEADING_ERROR = 0.05  # rad (~2.9 degrees)
STEPS = 800

def run_controller(controller_name, controller_func):
    """Run a controller and return metrics"""
    env = ResidualPathEnv()
    env.target_speed = 25.0
    env.reset()
    
    # Apply SAME initial error to ALL controllers
    env.state[0] = INITIAL_ERROR
    env.state[2] = INITIAL_HEADING_ERROR
    
    errors = []
    positions = []
    start_time = time.time()
    
    for step in range(STEPS):
        action = controller_func(env)
        _, _, _, _, info = env.step(action)
        errors.append(info['error'])
        positions.append(info['y_phys'])
    
    elapsed = time.time() - start_time
    rmse = np.sqrt(np.mean(np.square(errors)))
    max_error = np.max(np.abs(errors))
    
    return {
        'rmse': rmse,
        'max_error': max_error,
        'time': elapsed,
        'final_position': positions[-1]
    }

# ==========================================
# 1. LQR CONTROLLER
# ==========================================
print("\n1. Testing LQR...")
print("-" * 50)

def lqr_controller(env):
    steering = -np.dot(K_LQR, env.state)
    return np.array([np.clip(steering, -0.5, 0.5)])

lqr_results = run_controller("LQR", lqr_controller)
print(f"   LQR RMSE: {lqr_results['rmse']:.4f} m")
print(f"   LQR Max Error: {lqr_results['max_error']:.4f} m")
print(f"   Final Position: {lqr_results['final_position']:.2f} m")

# ==========================================
# 2. PURE PPO CONTROLLER
# ==========================================
print("\n2. Testing Pure PPO...")
print("-" * 50)

try:
    ppo_model = PPO.load('models/ppo_lans_final')
    print("   Loaded: ppo_lans_final")
    
    def ppo_controller(env):
        action, _ = ppo_model.predict(env._get_observation(), deterministic=True)
        return action
    
    ppo_results = run_controller("PPO", ppo_controller)
    print(f"   PPO RMSE: {ppo_results['rmse']:.4f} m")
    print(f"   PPO Max Error: {ppo_results['max_error']:.4f} m")
    print(f"   Final Position: {ppo_results['final_position']:.2f} m")
except Exception as e:
    print(f"   Error: {e}")
    ppo_results = None

# ==========================================
# 3. LANS (Residual PPO) CONTROLLER
# ==========================================
print("\n3. Testing LANS (Residual PPO)...")
print("-" * 50)

try:
    lans_model = PPO.load('models/residual/ppo_residual_final')
    print("   Loaded: ppo_residual_final")
    
    def lans_controller(env):
        action, _ = lans_model.predict(env._get_observation(), deterministic=True)
        return action
    
    lans_results = run_controller("LANS", lans_controller)
    print(f"   LANS RMSE: {lans_results['rmse']:.4f} m")
    print(f"   LANS Max Error: {lans_results['max_error']:.4f} m")
    print(f"   Final Position: {lans_results['final_position']:.2f} m")
except Exception as e:
    print(f"   Error: {e}")
    lans_results = None

# ==========================================
# FINAL RESULTS TABLE
# ==========================================
print("\n" + "=" * 70)
print("FINAL RESULTS (Same Initial Error: 0.5m lateral, 0.05rad heading)")
print("=" * 70)
print(f"{'Controller':<20} {'RMSE (m)':<12} {'Max Error (m)':<15}")
print("-" * 50)

all_results = []

if lqr_results:
    print(f"{'LQR':<20} {lqr_results['rmse']:<12.4f} {lqr_results['max_error']:<15.4f}")
    all_results.append(('LQR', lqr_results['rmse']))

if ppo_results:
    print(f"{'Pure PPO':<20} {ppo_results['rmse']:<12.4f} {ppo_results['max_error']:<15.4f}")
    all_results.append(('Pure PPO', ppo_results['rmse']))

if lans_results:
    print(f"{'LANS (Ours)':<20} {lans_results['rmse']:<12.4f} {lans_results['max_error']:<15.4f}")
    all_results.append(('LANS', lans_results['rmse']))

print("=" * 70)

# ==========================================
# COMPARISONS
# ==========================================
if lqr_results and lans_results:
    print("\n📊 COMPARISONS:")
    print("-" * 50)
    
    diff_lans_lqr = abs(lans_results['rmse'] - lqr_results['rmse'])
    pct_lans_vs_lqr = ((lqr_results['rmse'] - lans_results['rmse']) / lqr_results['rmse']) * 100
    
    if lans_results['rmse'] < lqr_results['rmse']:
        print(f"✅ LANS is {pct_lans_vs_lqr:.1f}% BETTER than LQR!")
        print(f"   LANS: {lans_results['rmse']:.4f}m vs LQR: {lqr_results['rmse']:.4f}m")
    else:
        print(f"⚠️ LANS is {abs(pct_lans_vs_lqr):.1f}% WORSE than LQR")
        print(f"   LQR: {lqr_results['rmse']:.4f}m vs LANS: {lans_results['rmse']:.4f}m")
        print(f"   Gap to beat LQR: {diff_lans_lqr:.4f}m")

if ppo_results and lans_results:
    pct_lans_vs_ppo = ((ppo_results['rmse'] - lans_results['rmse']) / ppo_results['rmse']) * 100
    if lans_results['rmse'] < ppo_results['rmse']:
        print(f"✅ LANS is {pct_lans_vs_ppo:.1f}% BETTER than Pure PPO!")
    else:
        print(f"⚠️ LANS is {abs(pct_lans_vs_ppo):.1f}% WORSE than Pure PPO")

# ==========================================
# BEST CONTROLLER
# ==========================================
if all_results:
    best = min(all_results, key=lambda x: x[1])
    print(f"\n🏆 BEST CONTROLLER: {best[0]} with RMSE = {best[1]:.4f} m")
