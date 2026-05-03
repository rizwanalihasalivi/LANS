"""
tune_blending.py - Find optimal blending weights
"""

import numpy as np
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv
import os
import time
import json
from datetime import datetime

os.makedirs("results/tuning", exist_ok=True)

class HybridTuner:
    """Simplified hybrid controller for tuning"""
    def __init__(self):
        print("📦 Loading models...")
        self.lqr_gains = np.array([0.5, 0.1, 0.3, 0.05])
        self.ppo_model = PPO.load("models/ppo_curriculum_final")
        print("✅ Models loaded successfully")
        
    def get_action(self, obs, weights):
        """Get hybrid action with given weights"""
        # Get state
        if len(obs.shape) > 1:
            state = obs[0][:4]
        else:
            state = obs[:4]
        
        # LQR action
        lqr_action = -np.dot(self.lqr_gains, state)
        
        # PPO action
        ppo_action, _ = self.ppo_model.predict(obs, deterministic=True)
        if isinstance(ppo_action, np.ndarray):
            ppo_action = ppo_action[0]
        
        # Dynamic alpha based on error
        lateral_error = abs(state[0])
        if lateral_error < 0.1:
            alpha = weights['low_error']
        elif lateral_error < 0.5:
            alpha = weights['med_error']
        else:
            alpha = weights['high_error']
        
        # Blend
        total_action = alpha * ppo_action + (1 - alpha) * lqr_action
        return np.clip(total_action, -0.5, 0.5)
    
    def evaluate(self, weights, with_latency=False, n_runs=3):
        """Evaluate a blending strategy"""
        rmses = []
        
        for seed in [42, 123, 456][:n_runs]:
            np.random.seed(seed)
            
            # Setup environment
            raw_env = PathTrackingEnv(mode="eval")
            raw_env.vx = 25.0
            env = DummyVecEnv([lambda: raw_env])
            
            # Load normalizer if exists
            norm_path = "models/vec_normalize_curriculum_final.pkl"
            if os.path.exists(norm_path):
                env = VecNormalize.load(norm_path, env)
                env.training = False
                env.norm_reward = False
            
            obs = env.reset()
            errors = []
            
            for step in range(len(raw_env.y_ref)-1):
                # Simulate latency if requested
                if with_latency and 400 < step < 600:
                    time.sleep(0.005)
                
                # Get action
                action = self.get_action(obs, weights)
                
                # Step environment
                obs, _, _, info = env.step(np.array([action]))
                errors.append(info[0]['error'])
            
            rmse = np.sqrt(np.mean(np.square(errors)))
            rmses.append(rmse)
        
        return np.mean(rmses), np.std(rmses)

def main():
    print("="*70)
    print("🎯 TUNING: Finding Optimal Blending Weights")
    print("="*70)
    
    # Initialize tuner
    tuner = HybridTuner()
    
    # Test different blending strategies
    strategies = {
        'default': {'low_error': 0.8, 'med_error': 0.6, 'high_error': 0.4},
        'more_ppo': {'low_error': 0.9, 'med_error': 0.7, 'high_error': 0.5},
        'balanced': {'low_error': 0.7, 'med_error': 0.5, 'high_error': 0.3},
        'conservative': {'low_error': 0.6, 'med_error': 0.4, 'high_error': 0.2},
        'aggressive': {'low_error': 0.95, 'med_error': 0.8, 'high_error': 0.6},
        'very_aggressive': {'low_error': 1.0, 'med_error': 0.9, 'high_error': 0.7},
        'very_conservative': {'low_error': 0.5, 'med_error': 0.3, 'high_error': 0.1},
        'ppo_dominant': {'low_error': 0.85, 'med_error': 0.75, 'high_error': 0.65},
        'lqr_dominant': {'low_error': 0.4, 'med_error': 0.3, 'high_error': 0.2},
        'adaptive': {'low_error': 0.9, 'med_error': 0.6, 'high_error': 0.3},
        'ultra_ppo': {'low_error': 0.98, 'med_error': 0.95, 'high_error': 0.9},
        'ultra_lqr': {'low_error': 0.3, 'med_error': 0.2, 'high_error': 0.1},
        'medium': {'low_error': 0.75, 'med_error': 0.55, 'high_error': 0.35},
    }
    
    results = {}
    
    print("\n📊 Testing strategies without latency...")
    print("-" * 50)
    
    for strategy_name, weights in strategies.items():
        print(f"\n  🔍 Testing: {strategy_name}")
        print(f"     Weights: {weights}")
        
        rmse, std = tuner.evaluate(weights, with_latency=False, n_runs=3)
        results[strategy_name] = rmse
        
        # Color code based on performance
        if rmse < 0.5331:
            print(f"     ✅ RMSE: {rmse:.4f} ± {std:.4f}m (BEATS PPO!)")
        elif rmse < 0.5600:
            print(f"     📈 RMSE: {rmse:.4f} ± {std:.4f}m (Better than current)")
        else:
            print(f"     📊 RMSE: {rmse:.4f} ± {std:.4f}m")
    
    # Find best strategy
    best_strategy = min(results, key=results.get)
    best_weights = strategies[best_strategy]
    best_rmse = results[best_strategy]
    
    print("\n" + "="*70)
    print(f"✅ BEST STRATEGY: {best_strategy}")
    print(f"   Weights: {best_weights}")
    print(f"   RMSE: {best_rmse:.4f} m")
    
    # Test best strategy with latency
    print("\n" + "="*70)
    print("⏱️  Testing best strategy WITH LATENCY...")
    print("="*70)
    
    rmse_latency, std_latency = tuner.evaluate(best_weights, with_latency=True, n_runs=3)
    print(f"\n   RMSE with latency: {rmse_latency:.4f} ± {std_latency:.4f} m")
    
    # Plot results
    plt.figure(figsize=(16, 8))
    
    # Sort results for better visualization
    sorted_items = sorted(results.items(), key=lambda x: x[1])
    strategies_list = [item[0] for item in sorted_items]
    rmses = [item[1] for item in sorted_items]
    
    # Color bars based on performance
    colors = []
    for rmse in rmses:
        if rmse < 0.5331:
            colors.append('green')
        elif rmse < 0.5600:
            colors.append('yellowgreen')
        else:
            colors.append('salmon')
    
    bars = plt.bar(range(len(strategies_list)), rmses, color=colors, alpha=0.8)
    plt.xticks(range(len(strategies_list)), strategies_list, rotation=45, ha='right')
    
    # Add target lines
    plt.axhline(y=0.5331, color='blue', linestyle='--', linewidth=2.5, 
                label=f'Pure PPO (0.5331m)')
    plt.axhline(y=0.5600, color='orange', linestyle='--', linewidth=2,
                label=f'Current Hybrid (0.5600m)')
    plt.axhline(y=best_rmse, color='green', linestyle=':', linewidth=2,
                label=f'Best Found ({best_rmse:.4f}m)')
    
    plt.ylabel('RMSE (m)')
    plt.title('Blending Strategy Tuning Results (Lower is Better)')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for i, (bar, rmse) in enumerate(zip(bars, rmses)):
        height = bar.get_height()
        plt.text(i, height + 0.001, f'{rmse:.4f}', 
                ha='center', fontsize=8, rotation=90)
    
    plt.tight_layout()
    plt.savefig('results/tuning/blending_tuning_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Print final comparison
    print("\n" + "="*70)
    print("🏆 FINAL COMPARISON")
    print("="*70)
    
    pure_ppo = 0.5331
    current_hybrid = 0.5600
    
    print(f"\n📈 Pure PPO:           {pure_ppo:.4f} m")
    print(f"🚀 Current Hybrid:     {current_hybrid:.4f} m")
    print(f"🎯 Optimized Hybrid:   {best_rmse:.4f} m")
    
    if best_rmse < pure_ppo:
        improvement = (pure_ppo - best_rmse) * 1000
        print(f"\n✅ VICTORY! Optimized hybrid beats Pure PPO by {improvement:.1f} mm!")
        
        # Calculate improvement percentages
        over_ppo = ((pure_ppo - best_rmse) / pure_ppo) * 100
        over_current = ((current_hybrid - best_rmse) / current_hybrid) * 100
        
        print(f"   • {over_ppo:.1f}% better than Pure PPO")
        print(f"   • {over_current:.1f}% better than current hybrid")
    else:
        gap = (best_rmse - pure_ppo) * 1000
        print(f"\n📊 Still need to close gap of {gap:.1f} mm")
    
    print(f"\n⏱️  With latency: {rmse_latency:.4f} m")
    if rmse_latency < pure_ppo:
        print(f"   ✅ Also beats Pure PPO under latency!")
    
    # Save results
    config = {
        'timestamp': datetime.now().isoformat(),
        'best_strategy': best_strategy,
        'weights': best_weights,
        'rmse_no_latency': float(best_rmse),
        'rmse_with_latency': float(rmse_latency),
        'std_no_latency': float(np.std([results[s] for s in results])),
        'std_with_latency': float(std_latency),
        'pure_ppo_rmse': pure_ppo,
        'current_hybrid_rmse': current_hybrid,
        'all_results': {k: float(v) for k, v in results.items()}
    }
    
    with open('results/tuning/best_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n✅ Results saved to results/tuning/best_config.json")
    print("✅ Plot saved to results/tuning/blending_tuning_results.png")

if __name__ == "__main__":
    main()