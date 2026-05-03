import numpy as np
import time
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from envs.path_tracking_env import PathTrackingEnv

def final_profile():
    raw_env = PathTrackingEnv(mode="eval")
    env = DummyVecEnv([lambda: raw_env])
    env = VecNormalize.load("models/vec_normalize_curriculum_final.pkl", env)
    model = PPO.load("models/ppo_curriculum_final")
    
    obs = env.reset()
    latencies = []
    
    print("⏲️ Final Performance Profiling in progress...")
    
    # Run 1000 steps to get a statistically significant average
    for _ in range(1000):
        start = time.time()
        action, _ = model.predict(obs, deterministic=True)
        # We only measure inference time (the "AI thinking" part)
        latencies.append(time.time() - start)
        obs, _, _, _ = env.step(action)
        
    avg_latency_ms = np.mean(latencies) * 1000
    hz = 1 / np.mean(latencies)
    max_latency_ms = np.max(latencies) * 1000
    
    print("-" * 30)
    print(f"✅ BENCHMARK COMPLETE (Legacy Hardware: MacBook Air 2012)")
    print(f"🔹 Average Latency: {avg_latency_ms:.2f} ms")
    print(f"🔹 Inference Speed: {hz:.2f} Hz")
    print(f"🔹 Peak Latency (Worst Case): {max_latency_ms:.2f} ms")
    print("-" * 30)
    
    return avg_latency_ms, hz

if __name__ == "__main__":
    final_profile()