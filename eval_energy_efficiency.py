import psutil
import time
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from envs.path_tracking_env import PathTrackingEnv

def measure_energy_impact():
    # 1. Properly wrap the environment for SB3
    # This prevents the ValueError by handling the observation correctly
    def make_env():
        return PathTrackingEnv(mode="eval")
    
    env = DummyVecEnv([make_env])
    model = PPO.load("models/ppo_curriculum_final")
    
    results = []
    
    # Test Scenarios: Low Latency vs High Latency (Conservative)
    for mode in ["Standard", "Latency_Aware"]:
        print(f"🔋 Measuring Energy for {mode} Mode...")
        
        # Reset returns a NumPy array in VecEnv API
        obs = env.reset()
        cpu_usage = []
        start_time = time.time()
        
        for _ in range(500): 
            # Inject delay to trigger conservative behavior in Latency_Aware mode
            if mode == "Latency_Aware":
                time.sleep(0.05) 
            
            # Predict now receives the correct array format
            action, _ = model.predict(obs, deterministic=True)
            obs, _, _, _ = env.step(action)
            
            # Sample CPU usage
            cpu_usage.append(psutil.cpu_percent(interval=None))
            
        duration = time.time() - start_time
        avg_cpu = np.mean(cpu_usage)
        
        # Power estimation for MacBook Air 2012 (TDP ~17W)
        # Base idle (~5W) + Load-dependent draw
        est_power_w = 5 + (avg_cpu / 100) * 12 
        total_energy_j = est_power_w * duration
        
        results.append({
            "Mode": mode,
            "Avg_CPU_Percent": avg_cpu,
            "Est_Power_W": est_power_w,
            "Total_Energy_J": total_energy_j,
            "Duration_sec": duration
        })

    df = pd.DataFrame(results)
    df.to_csv("energy_innovation_results.csv", index=False)
    print("\n" + "="*30)
    print("✅ Energy Analysis Complete!")
    print(df[['Mode', 'Avg_CPU_Percent', 'Total_Energy_J']])
    print("="*30)

if __name__ == "__main__":
    measure_energy_impact()