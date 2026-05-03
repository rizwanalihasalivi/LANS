"""
train_curriculum.py - Curriculum Learning for LANS Controller
Implements 3-stage training: Low Speed → Target Speed → Fine-tuning with Latency
"""

import os
import sys
import random
import numpy as np
import tensorflow as tf
import logging
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
SEED = 42
LOG_LEVEL = logging.INFO

# Set random seeds for reproducibility
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/training_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# IMPORT VALIDATION
# ==========================================
try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    logger.info("✅ Successfully imported stable-baselines3")
except ImportError as e:
    logger.error(f"❌ Failed to import stable-baselines3: {e}")
    logger.error("Install with: pip install stable-baselines3")
    sys.exit(1)

try:
    import gymnasium as gym
    logger.info("✅ Successfully imported gymnasium")
except ImportError as e:
    logger.error(f"❌ Failed to import gymnasium: {e}")
    logger.error("Install with: pip install gymnasium")
    sys.exit(1)

try:
    from envs.path_tracking_env import PathTrackingEnv
    logger.info("✅ Successfully imported PathTrackingEnv")
except ImportError as e:
    logger.error(f"❌ Failed to import PathTrackingEnv: {e}")
    logger.error("Make sure envs/path_tracking_env.py exists")
    sys.exit(1)

# ==========================================
# CREATE OUTPUT DIRECTORIES
# ==========================================
os.makedirs("models", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("models/checkpoints", exist_ok=True)

# ==========================================
# ENVIRONMENT CREATION
# ==========================================
def create_env(vx=15.0, mode="train"):
    """
    Create vectorized and normalized environment for training
    
    Args:
        vx (float): Vehicle speed in m/s
        mode (str): "train" or "eval"
    
    Returns:
        VecNormalize: Vectorized environment with normalization
    """
    def make_env():
        env = PathTrackingEnv(mode=mode)
        env.vx = vx
        return env
    
    # Vectorize environment
    env = DummyVecEnv([make_env])
    
    # Add normalization wrapper (for stable training)
    env = VecNormalize(
        env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=10.0,
        clip_reward=10.0,
        gamma=0.99
    )
    
    logger.info(f"Created environment: mode={mode}, vx={vx} m/s ({vx*3.6:.0f} km/h)")
    return env

# ==========================================
# CHECKPOINT CALLBACK
# ==========================================
checkpoint_callback = CheckpointCallback(
    save_freq=50000,  # Save every 50,000 steps
    save_path="./models/checkpoints/",
    name_prefix="ppo_curriculum",
    save_replay_buffer=False,
    save_vecnormalize=True
)

# ==========================================
# MAIN TRAINING FUNCTION
# ==========================================
def main():
    """Main curriculum learning training loop"""
    
    print("\n" + "="*70)
    print("🏎️  LANS CONTROLLER: CURRICULUM LEARNING")
    print("="*70)
    logger.info("Starting curriculum learning training...")
    
    # ==========================================
    # STAGE 1: Low Speed Training (15 m/s = 54 km/h)
    # ==========================================
    print("\n" + "-"*50)
    print("[STAGE 1/3] Training at 15 m/s (54 km/h) for stability")
    print("-"*50)
    logger.info("Stage 1: Low speed training (15 m/s)")
    
    env_stage1 = create_env(vx=15.0, mode="train")
    
    # Create PPO model
    model = PPO(
        "MlpPolicy",
        env_stage1,
        learning_rate=1e-4,
        ent_coef=0.01,
        n_epochs=20,
        batch_size=64,
        n_steps=2048,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        verbose=1,
        seed=SEED,
        tensorboard_log="./logs/tensorboard/"
    )
    
    logger.info("Training for 200,000 timesteps...")
    model.learn(
        total_timesteps=200_000,
        callback=checkpoint_callback,
        log_interval=10,
        reset_num_timesteps=True
    )
    logger.info("✅ Stage 1 complete")
    print("✅ Stage 1 Complete")
    
    # Save Stage 1 model
    model.save("models/ppo_stage1_15ms")
    logger.info("Model saved: models/ppo_stage1_15ms.zip")
    
    # ==========================================
    # STAGE 2: Target Speed Training (25 m/s = 90 km/h)
    # ==========================================
    print("\n" + "-"*50)
    print("[STAGE 2/3] Scaling to 25 m/s (90 km/h) for high-speed tracking")
    print("-"*50)
    logger.info("Stage 2: Target speed training (25 m/s)")
    
    # Update environment speed
    env_stage1.set_attr("vx", 25.0)
    logger.info("Updated environment speed to 25 m/s")
    
    logger.info("Training for 400,000 additional timesteps...")
    model.learn(
        total_timesteps=400_000,
        callback=checkpoint_callback,
        log_interval=10,
        reset_num_timesteps=False
    )
    logger.info("✅ Stage 2 complete")
    print("✅ Stage 2 Complete")
    
    # Save Stage 2 model
    model.save("models/ppo_stage2_25ms")
    logger.info("Model saved: models/ppo_stage2_25ms.zip")
    
    # ==========================================
    # STAGE 3: Fine-tuning with Latency Injection
    # ==========================================
    print("\n" + "-"*50)
    print("[STAGE 3/3] Fine-tuning with latency injection (5-130 ms jitter)")
    print("-"*50)
    logger.info("Stage 3: Latency-aware fine-tuning")
    
    # Note: Latency injection is handled inside the environment
    # (the _compute_adaptive_gain and step() functions already include latency)
    
    logger.info("Training for 200,000 additional timesteps...")
    model.learn(
        total_timesteps=200_000,
        callback=checkpoint_callback,
        log_interval=10,
        reset_num_timesteps=False
    )
    logger.info("✅ Stage 3 complete")
    print("✅ Stage 3 Complete")
    
    # ==========================================
    # SAVE FINAL MODEL
    # ==========================================
    print("\n" + "-"*50)
    print("SAVING FINAL MODEL")
    print("-"*50)
    
    # Save final model
    model.save("models/ppo_curriculum_final")
    logger.info("✅ Model saved to: models/ppo_curriculum_final.zip")
    print("✅ Model saved to: models/ppo_curriculum_final.zip")
    
    # Save normalization statistics
    env_stage1.save("models/vec_normalize_curriculum_final.pkl")
    logger.info("✅ Normalization saved to: models/vec_normalize_curriculum_final.pkl")
    print("✅ Normalization saved to: models/vec_normalize_curriculum_final.pkl")
    
    # ==========================================
    # SUMMARY
    # ==========================================
    print("\n" + "="*70)
    print("✅ CURRICULUM LEARNING COMPLETE!")
    print("="*70)
    print(f"Total timesteps trained: 800,000")
    print(f"Stages: 3 (15 m/s → 25 m/s → latency fine-tuning)")
    print(f"Random seed: {SEED}")
    print("="*70)
    
    logger.info("Curriculum learning training completed successfully!")
    
    # Clean up
    env_stage1.close()

# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\nTraining interrupted by user")
        print("\n⚠️ Training interrupted. Partial model may have been saved.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed with error: {e}", exc_info=True)
        print(f"\n❌ Training failed: {e}")
        sys.exit(1)