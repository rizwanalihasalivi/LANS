"""
train_ppo.py - Train LANS Controller with Latency-Aware PPO
Implements:
- LQR baseline + PPO residual
- Latency measurement and adaptive gain β(τ)
- Latency penalty in reward function
- Curriculum learning (15 m/s → 25 m/s → latency fine-tuning)
"""

import os
import sys
import time
import random
import numpy as np
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

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/train_ppo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
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
os.makedirs("models/checkpoints", exist_ok=True)
os.makedirs("logs/tensorboard", exist_ok=True)

# ==========================================
# ENVIRONMENT CREATION
# ==========================================
def create_env(vx=25.0, mode="train"):
    """
    Create vectorized and normalized environment
    
    Args:
        vx (float): Vehicle speed (m/s)
        mode (str): "train" or "eval"
    
    Returns:
        VecNormalize: Vectorized environment
    """
    def make_env():
        env = PathTrackingEnv(mode=mode)
        env.vx = vx
        return env
    
    # Vectorize environment
    env = DummyVecEnv([make_env])
    
    # Add normalization wrapper
    env = VecNormalize(
        env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=10.0,
        clip_reward=10.0,
        gamma=0.99,
        norm_obs_keys=None
    )
    
    logger.info(f"Created environment: mode={mode}, vx={vx} m/s ({vx*3.6:.0f} km/h)")
    return env

# ==========================================
# CHECKPOINT CALLBACK
# ==========================================
checkpoint_callback = CheckpointCallback(
    save_freq=50000,
    save_path="./models/checkpoints/",
    name_prefix="ppo_lans",
    save_replay_buffer=False,
    save_vecnormalize=True
)

# ==========================================
# TRAINING FUNCTION
# ==========================================
def train_curriculum():
    """
    Curriculum learning with 3 stages:
    1. Low speed (15 m/s) - Learn basic tracking
    2. Target speed (25 m/s) - High-speed adaptation
    3. Latency fine-tuning - Learn latency awareness
    """
    
    print("\n" + "="*70)
    print("🚀 LANS CONTROLLER: LATENCY-AWARE PPO TRAINING")
    print("="*70)
    logger.info("Starting curriculum learning with seed=%d", SEED)
    
    # ==========================================
    # STAGE 1: LOW SPEED (15 m/s = 54 km/h)
    # ==========================================
    print("\n" + "-"*60)
    print("[STAGE 1/3] Training at 15 m/s (54 km/h) for stability")
    print("-"*60)
    logger.info("Stage 1: Low speed training (15 m/s)")
    
    env_stage1 = create_env(vx=15.0, mode="train")
    
    # Create PPO model
    model = PPO(
        "MlpPolicy",
        env_stage1,
        learning_rate=3e-4,
        ent_coef=0.01,
        n_epochs=10,
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
    
    # Save checkpoint
    model.save("models/ppo_stage1_15ms")
    logger.info("Model saved: models/ppo_stage1_15ms.zip")
    
    # ==========================================
    # STAGE 2: TARGET SPEED (25 m/s = 90 km/h)
    # ==========================================
    print("\n" + "-"*60)
    print("[STAGE 2/3] Scaling to 25 m/s (90 km/h) for high-speed tracking")
    print("-"*60)
    logger.info("Stage 2: Target speed training (25 m/s)")
    
    # Update environment speed
    env_stage1.set_attr("vx", 25.0)
    logger.info("Updated environment speed to 25 m/s")
    
    # Reduce learning rate for fine-tuning
    model.learning_rate = 1e-4
    logger.info("Learning rate reduced to 1e-4")
    
    logger.info("Training for 400,000 additional timesteps...")
    model.learn(
        total_timesteps=400_000,
        callback=checkpoint_callback,
        log_interval=10,
        reset_num_timesteps=False
    )
    logger.info("✅ Stage 2 complete")
    print("✅ Stage 2 Complete")
    
    # Save checkpoint
    model.save("models/ppo_stage2_25ms")
    logger.info("Model saved: models/ppo_stage2_25ms.zip")
    
    # ==========================================
    # STAGE 3: LATENCY FINE-TUNING
    # ==========================================
    print("\n" + "-"*60)
    print("[STAGE 3/3] Fine-tuning with latency injection (5-130 ms jitter)")
    print("-"*60)
    logger.info("Stage 3: Latency-aware fine-tuning")
    
    # Note: Latency injection and β(τ) are handled inside PathTrackingEnv
    # The reward already includes latency penalty (Equation 40)
    
    logger.info("Training for 400,000 additional timesteps...")
    model.learn(
        total_timesteps=400_000,
        callback=checkpoint_callback,
        log_interval=10,
        reset_num_timesteps=False
    )
    logger.info("✅ Stage 3 complete")
    print("✅ Stage 3 Complete")
    
    # ==========================================
    # SAVE FINAL MODEL
    # ==========================================
    print("\n" + "-"*60)
    print("SAVING FINAL MODEL")
    print("-"*60)
    
    # Save final model
    MODEL_PATH = "models/ppo_lans_final"
    model.save(MODEL_PATH)
    logger.info(f"✅ Model saved to: {MODEL_PATH}.zip")
    print(f"✅ Model saved to: {MODEL_PATH}.zip")
    
    # Save normalization statistics
    NORM_PATH = "models/vec_normalize_lans_final.pkl"
    env_stage1.save(NORM_PATH)
    logger.info(f"✅ Normalization saved to: {NORM_PATH}")
    print(f"✅ Normalization saved to: {NORM_PATH}")
    
    # ==========================================
    # SUMMARY
    # ==========================================
    print("\n" + "="*70)
    print("✅ TRAINING COMPLETE!")
    print("="*70)
    print(f"Total timesteps trained: 1,000,000")
    print(f"Stages: 3 (15 m/s → 25 m/s → latency fine-tuning)")
    print(f"Random seed: {SEED}")
    print("="*70)
    
    # Close environment
    env_stage1.close()
    
    logger.info("Training completed successfully!")


# ==========================================
# SIMPLE TRAINING (No Curriculum)
# ==========================================
def train_simple():
    """
    Simple single-stage training (for quick testing)
    """
    print("\n" + "="*70)
    print("🚀 LANS CONTROLLER: SIMPLE PPO TRAINING")
    print("="*70)
    logger.info("Starting simple training with seed=%d", SEED)
    
    # Create environment
    env = create_env(vx=25.0, mode="train")
    
    # Create PPO model
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        ent_coef=0.01,
        n_epochs=10,
        batch_size=64,
        n_steps=2048,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        verbose=1,
        seed=SEED,
        tensorboard_log="./logs/tensorboard/"
    )
    
    logger.info("Training for 500,000 timesteps...")
    model.learn(
        total_timesteps=500_000,
        callback=checkpoint_callback,
        log_interval=10
    )
    
    # Save model
    MODEL_PATH = "models/ppo_lans_simple"
    model.save(MODEL_PATH)
    env.save("models/vec_normalize_lans_simple.pkl")
    
    logger.info(f"✅ Model saved to: {MODEL_PATH}.zip")
    print(f"✅ Model saved to: {MODEL_PATH}.zip")
    
    env.close()
    print("✅ Training Complete!")


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    try:
        # Run curriculum training (recommended)
        train_curriculum()
        
        # Or run simple training for quick testing
        # train_simple()
        
    except KeyboardInterrupt:
        logger.warning("\nTraining interrupted by user")
        print("\n⚠️ Training interrupted. Partial model may have been saved.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed with error: {e}", exc_info=True)
        print(f"\n❌ Training failed: {e}")
        sys.exit(1)