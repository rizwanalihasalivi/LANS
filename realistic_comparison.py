from stable_baselines3 import PPO
from envs.residual_path_env import ResidualPathEnv
import numpy as np

print("=" * 70)
print("FAIR COMPARISON (With Initial Disturbance)")
print("=" * 70)

K_LQR = np.array([0.52, 0.12, 0.31, 0.04])

# ==========================================
# LQR WITH INITIAL ERROR (Realistic)
# ==========================================
print("\n1. LQR with Initial Lateral Error (0.5m)...")
print("-" * 50)

env = ResidualPathEnv()
env.target_speed = 25.0
env.reset()
env.state[0] = 0.5  # Add 0.5m initial lateral error
env.state[2] = 0.05 # Add 0.05 rad heading error

lqr_errors = []
lqr_y = []

for step in range(800):
    steering = -np.dot(K_LQR, env.state)
    steering = np.clip(steering, -0.5, 0.5)
    _, _, _, _, info = env.step(np.array([steering]))
    lqr_errors.append(info['error'])
    lqr_y.append(info['y_phys'])

lqr_rmse = np.sqrt(np.mean(np.square(lqr_errors)))
print(f"LQR RMSE: {lqr_rmse:.4f} m")

# ==========================================
# PURE PPO (Same initial error)
# ==========================================
print("\n2. Pure PPO with Initial Lateral Error...")
print("-" * 50)

ppo_model = PPO.load('models/ppo_lans_final')
env = ResidualPathEnv()
env.target_speed = 25.0
env.reset()
env.state[0] = 0.5
env.state[2] = 0.05

ppo_errors = []

for step in range(800):
    action, _ = ppo_model.predict(env._get_observation(), deterministic=True)
    _, _, _, _, info = env.step(action)
    ppo_errors.append(info['error'])

ppo_rmse = np.sqrt(np.mean(np.square(ppo_errors)))
print(f"PPO RMSE: {ppo_rmse:.4f} m")

# ==========================================
# LANS (Same initial error)
# ==========================================
print("\n3. LANS with Initial Lateral Error...")
print("-" * 50)

lans_model = PPO.load('models/residual/ppo_residual_final')
env = ResidualPathEnv()
env.target_speed = 25.0
env.reset()
env.state[0] = 0.5
env.state[2] = 0.05

lans_errors = []

for step in range(800):
    action, _ = lans_model.predict(env._get_observation(), deterministic=True)
    _, _, _, _, info = env.step(action)
    lans_errors.append(info['error'])

lans_rmse = np.sqrt(np.mean(np.square(lans_errors)))
print(f"LANS RMSE: {lans_rmse:.4f} m")

# ==========================================
# RESULTS
# ==========================================
print("\n" + "=" * 70)
print("RESULTS (With Initial 0.5m Lateral Error)")
print("=" * 70)
print(f"  LQR:          {lqr_rmse:.4f} m")
print(f"  Pure PPO:     {ppo_rmse:.4f} m")
print(f"  LANS (Ours):  {lans_rmse:.4f} m")
print("=" * 70)

if lans_rmse < lqr_rmse:
    print(f"\n✅ LANS is {((lqr_rmse - lans_rmse) / lqr_rmse) * 100:.1f}% BETTER than LQR!")
if lans_rmse < ppo_rmse:
    print(f"✅ LANS is {((ppo_rmse - lans_rmse) / ppo_rmse) * 100:.1f}% BETTER than Pure PPO!")
