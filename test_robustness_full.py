# test_robustness_full.py
import numpy as np
import matplotlib.pyplot as plt
import os
import time
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv

MASSES = [1100, 1300, 1500, 1650, 1800, 2000, 2200]
K_LQR = np.array([0.52, 0.12, 0.31, 0.04])

def run_robustness_test(mass_value):
    raw_env = PathTrackingEnv(mode="eval")
    raw_env.vx = 25.0
    
    # Update mass
    raw_env.params["m"] = mass_value
    lf, lr = raw_env.params["lf"], raw_env.params["lr"]
    raw_env.params["Iz"] = mass_value * ((lf + lr) ** 2) / 10
    raw_env.K_lqr = K_LQR
    
    raw_env.reset()
    
    # Run for FULL path length (1000 steps = 10 seconds = 250m)
    # This covers both lane changes (at 20m and 70m)
    
    env = DummyVecEnv([lambda: raw_env])
    
    stats_path = "models/vec_normalize_lans_final.pkl"
    if os.path.exists(stats_path):
        env = VecNormalize.load(stats_path, env)
        env.training = False
        env.norm_reward = False
    
    model = PPO.load('models/ppo_lans_final')
    
    obs = env.reset()
    errors = []
    positions = []
    x_positions = []
    
    # Run ALL steps (full 10 seconds = 1000 steps)
    max_steps = len(raw_env.y_ref) - 1
    
    for step in range(max_steps):
        t_start = time.perf_counter()
        current_state = raw_env.state if hasattr(raw_env, 'state') else np.zeros(4)
        
        delta_lqr = -np.dot(K_LQR, current_state)
        delta_lqr = np.clip(delta_lqr, -0.5, 0.5)
        
        action, _ = model.predict(obs, deterministic=True)
        delta_rl = action[0]
        
        tau_current = (time.perf_counter() - t_start) * 1000
        beta = np.exp(-(tau_current - 5) / 20) if tau_current >= 5 else 1.0
        
        delta_total = delta_lqr + beta * delta_rl
        delta_total = np.clip(delta_total, -0.5, 0.5)
        
        obs, _, _, info = env.step(np.array([delta_total]))
        
        error = info[0]["error"]
        errors.append(error)
        positions.append(raw_env.y_actual)
        x_positions.append(raw_env.x_position)
        
        if step % 200 == 0:
            print(f"  Step {step}: x={raw_env.x_position:.1f}m, error={error:.4f}m")
        
        if info[0].get('done', False):
            break
    
    rmse = np.sqrt(np.mean(np.square(errors)))
    max_error = np.max(np.abs(errors))
    
    return {
        'rmse': rmse, 
        'max_error': max_error,
        'errors': errors,
        'x_positions': x_positions,
        'positions': positions
    }

if __name__ == "__main__":
    os.makedirs("fresh_figures", exist_ok=True)
    
    print("=" * 60)
    print("MASS ROBUSTNESS TEST (FULL PATH)")
    print("=" * 60)
    
    all_results = {}
    
    for mass in MASSES:
        print(f"\nTesting mass: {mass} kg...")
        result = run_robustness_test(mass)
        all_results[mass] = result
        print(f"  RMSE: {result['rmse']:.4f} m")
        print(f"  Max error: {result['max_error']:.4f} m")
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    nominal_rmse = all_results[1650]['rmse']
    for mass, result in all_results.items():
        degradation = ((result['rmse'] - nominal_rmse) / nominal_rmse) * 100
        print(f"  {mass} kg: {result['rmse']:.4f} m ({degradation:+.1f}%)")
    
    # Plot trajectory for nominal mass
    result_1650 = all_results[1650]
    
    plt.figure(figsize=(12, 6))
    plt.plot(result_1650['x_positions'], result_1650['positions'], 'b-', linewidth=2, label='LANS Actual')
    plt.xlabel('Distance (m)')
    plt.ylabel('Lateral Position (m)')
    plt.title('LANS Trajectory on Double Lane Change (1650 kg)')
    plt.grid(True, alpha=0.3)
    plt.savefig('fresh_figures/lans_trajectory.png', dpi=300)
    print("\n✅ Trajectory plot saved to fresh_figures/lans_trajectory.png")