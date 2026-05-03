from stable_baselines3 import PPO
from envs.residual_path_env import ResidualPathEnv
import numpy as np

print("=" * 70)
print("FINAL REAL RMSE TEST - LANS CONTROLLER")
print("=" * 70)

# Load your best LANS model
print("\nLoading LANS model...")
model = PPO.load('models/residual/ppo_residual_final')
print("✅ Model loaded: ppo_residual_final")

# Create environment
env = ResidualPathEnv()
env.target_speed = 25.0

# Run 5 times for average
n_runs = 5
all_rmses = []

print("\nRunning 5 tests...")
print("-" * 50)

for run in range(n_runs):
    env.reset()
    errors = []
    
    for step in range(800):
        action, _ = model.predict(env._get_observation(), deterministic=True)
        _, _, _, _, info = env.step(action)
        errors.append(info['error'])
    
    rmse = np.sqrt(np.mean(np.square(errors)))
    max_error = np.max(np.abs(errors))
    all_rmses.append(rmse)
    
    print(f"Run {run+1}: RMSE = {rmse:.4f} m, Max Error = {max_error:.4f} m")

# Statistics
mean_rmse = np.mean(all_rmses)
std_rmse = np.std(all_rmses)
min_rmse = np.min(all_rmses)
max_rmse = np.max(all_rmses)

print("\n" + "=" * 70)
print("FINAL RESULTS")
print("=" * 70)
print(f"Mean RMSE:    {mean_rmse:.4f} m")
print(f"Std Dev:      {std_rmse:.4f} m")
print(f"Min RMSE:     {min_rmse:.4f} m")
print(f"Max RMSE:     {max_rmse:.4f} m")
print("=" * 70)

# Compare to LQR
lqr_rmse = 0.077  # From your earlier test
gap = mean_rmse - lqr_rmse
pct_gap = (gap / lqr_rmse) * 100

print(f"\n📊 Comparison:")
print(f"   LQR RMSE:      {lqr_rmse:.4f} m")
print(f"   LANS RMSE:     {mean_rmse:.4f} m")
print(f"   Difference:    {gap:.4f} m ({pct_gap:.1f}% worse than LQR)")

if mean_rmse < 0.25:
    print("\n✅ EXCELLENT! LANS is very close to LQR!")
elif mean_rmse < 0.35:
    print("\n✅ GOOD! LANS performance is acceptable!")
elif mean_rmse < 0.50:
    print("\n⚠️ ACCEPTABLE but can be improved with more training")
else:
    print("\n❌ NEEDS IMPROVEMENT - train longer")

print("\n" + "=" * 70)
print("DEFINITIVE ANSWER")
print("=" * 70)
print(f"YOUR REAL LANS RMSE = {mean_rmse:.4f} ± {std_rmse:.4f} m")
print("=" * 70)
