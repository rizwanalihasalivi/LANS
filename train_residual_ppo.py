"""
train_residual_ppo.py - Train LANS Controller with Residual PPO
Implements:
- LQR baseline + PPO residual (δ_total = δ_LQR + β·δ_RL)
- Latency measurement and adaptive gain β(τ)
- Latency penalty in reward function
- Curriculum learning (15 m/s → 25 m/s → latency fine-tuning)
"""

import os
import sys
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
        logging.FileHandler(f'logs/train_residual_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# IMPORT VALIDATION
# ==========================================
try:
    import gymnasium as gym
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    logger.info("Successfully imported stable-baselines3 and gymnasium")
except ImportError as e:
    logger.error(f"Failed to import required packages: {e}")
    logger.error("Install with: pip install stable-baselines3 gymnasium")
    sys.exit(1)

try:
    from envs.residual_path_env import ResidualPathEnv
    logger.info("Successfully imported ResidualPathEnv")
except ImportError as e:
    logger.error(f"Failed to import ResidualPathEnv: {e}")
    logger.error("Make sure envs/residual_path_env.py exists")
    sys.exit(1)

# ==========================================
# CREATE OUTPUT DIRECTORIES
# ==========================================
os.makedirs("models/residual", exist_ok=True)
os.makedirs("models/residual/checkpoints", exist_ok=True)
os.makedirs("logs/tensorboard", exist_ok=True)

# ==========================================
# ENVIRONMENT CREATION
# ==========================================
def create_env(vx=25.0):
    """
    Create vectorized and normalized environment
    
    Args:
        vx (float): Vehicle speed (m/s)
    
    Returns:
        VecNormalize: Vectorized environment
    """
    def make_env():
        env = ResidualPathEnv()
        env.target_speed = vx
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
        gamma=0.99
    )
    
    logger.info(f"Created environment: vx={vx} m/s ({vx*3.6:.0f} km/h)")
    return env

# ==========================================
# CHECKPOINT CALLBACK
# ==========================================
checkpoint_callback = CheckpointCallback(
    save_freq=50000,
    save_path='./models/residual/checkpoints/',
    name_prefix="ppo_residual",
    save_replay_buffer=False,
    save_vecnormalize=True
)

# ==========================================
# MODEL CONFIGURATION
# ==========================================
def create_model(env, learning_rate=1e-4):
    """Create PPO model with LANS-specific hyperparameters"""
    return PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=learning_rate,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        tensorboard_log="./logs/tensorboard/",
        seed=SEED,
        device="cpu"
    )

# ==========================================
# CURRICULUM TRAINING
# ==========================================
def train_curriculum():
    """
    Curriculum learning with 3 stages:
    1. Low speed (15 m/s) - Learn basic tracking
    2. Target speed (25 m/s) - High-speed adaptation
    3. Latency fine-tuning - Learn latency awareness
    """
    
    print("\n" + "="*80)
    print("LANS CONTROLLER: RESIDUAL PPO TRAINING (Curriculum)")
    print("="*80)
    logger.info("Starting curriculum learning with seed=%d", SEED)
    
    # ==========================================
    # STAGE 1: LOW SPEED (15 m/s = 54 km/h)
    # ==========================================
    print("\n" + "-"*60)
    print("[STAGE 1/3] Training at 15 m/s (54 km/h) for stability")
    print("-"*60)
    logger.info("Stage 1: Low speed training (15 m/s)")
    
    env_stage1 = create_env(vx=15.0)
    
    model = create_model(env_stage1, learning_rate=3e-4)
    
    logger.info("Training for 200,000 timesteps...")
    model.learn(
        total_timesteps=200_000,
        callback=checkpoint_callback,
        reset_num_timesteps=True
    )
    logger.info("Stage 1 complete")
    print("Stage 1 Complete")
    
    # Save checkpoint
    model.save("models/residual/ppo_residual_stage1")
    logger.info("Model saved: models/residual/ppo_residual_stage1.zip")
    
    # ==========================================
    # STAGE 2: TARGET SPEED (25 m/s = 90 km/h)
    # ==========================================
    print("\n" + "-"*60)
    print("[STAGE 2/3] Scaling to 25 m/s (90 km/h) for high-speed tracking")
    print("-"*60)
    logger.info("Stage 2: Target speed training (25 m/s)")
    
    # Update environment speed
    env_stage1.set_attr("target_speed", 25.0)
    logger.info("Updated environment speed to 25 m/s")
    
    # Reduce learning rate for fine-tuning
    model.learning_rate = 1e-4
    
    logger.info("Training for 400,000 additional timesteps...")
    model.learn(
        total_timesteps=400_000,
        callback=checkpoint_callback,
        reset_num_timesteps=False
    )
    logger.info("Stage 2 complete")
    print("Stage 2 Complete")
    
    # Save checkpoint
    model.save("models/residual/ppo_residual_stage2")
    logger.info("Model saved: models/residual/ppo_residual_stage2.zip")
    
    # ==========================================
    # STAGE 3: LATENCY FINE-TUNING
    # ==========================================
    print("\n" + "-"*60)
    print("[STAGE 3/3] Fine-tuning with latency injection (5-130 ms jitter)")
    print("-"*60)
    logger.info("Stage 3: Latency-aware fine-tuning")
    
    # Further reduce learning rate for final fine-tuning
    model.learning_rate = 5e-5
    logger.info("Learning rate reduced to 5e-5")
    
    logger.info("Training for 400,000 additional timesteps...")
    model.learn(
        total_timesteps=400_000,
        callback=checkpoint_callback,
        reset_num_timesteps=False
    )
    logger.info("Stage 3 complete")
    print("Stage 3 Complete")
    
    # ==========================================
    # SAVE FINAL MODEL
    # ==========================================
    print("\n" + "-"*60)
    print("SAVING FINAL MODEL")
    print("-"*60)
    
    # Save final model
    model.save("models/residual/ppo_residual_final")
    logger.info("Model saved to: models/residual/ppo_residual_final.zip")
    print("Model saved to: models/residual/ppo_residual_final.zip")
    
    # Save normalization statistics
    env_stage1.save("models/residual/vec_normalize_residual_final.pkl")
    logger.info("Normalization saved to: models/residual/vec_normalize_residual_final.pkl")
    print("Normalization saved to: models/residual/vec_normalize_residual_final.pkl")
    
    # ==========================================
    # SUMMARY
    # ==========================================
    print("\n" + "="*80)
    print("TRAINING COMPLETE!")
    print("="*80)
    print(f"Total timesteps trained: 1,000,000")
    print(f"Stages: 3 (15 m/s -> 25 m/s -> latency fine-tuning)")
    print(f"Random seed: {SEED}")
    print("="*80)
    
    logger.info("Training completed successfully!")
    env_stage1.close()


# ==========================================
# SIMPLE TRAINING (Single Stage)
# ==========================================
def train_simple():
    """
    Simple single-stage training (for quick testing)
    """
    print("\n" + "="*80)
    print("LANS CONTROLLER: RESIDUAL PPO TRAINING (Simple)")
    print("="*80)
    logger.info("Starting simple training with seed=%d", SEED)
    
    # Create environment (25 m/s)
    env = create_env(vx=25.0)
    
    # Create model
    model = create_model(env, learning_rate=3e-4)
    
    print("\nStarting Residual PPO Training...")
    logger.info("Training for 300,000 timesteps...")
    
    try:
        model.learn(
            total_timesteps=300_000,
            callback=checkpoint_callback
        )
        print("\nTraining Success!")
        logger.info("Training completed successfully")
    except KeyboardInterrupt:
        print("\nTraining interrupted by user. Saving partial model...")
        logger.warning("Training interrupted by user")
    
    # Save Final Results
    model.save("models/residual/ppo_residual_final")
    env.save("models/residual/vec_normalize_residual_final.pkl")
    
    logger.info("Model saved to: models/residual/ppo_residual_final.zip")
    print("Model saved to: models/residual/ppo_residual_final.zip")
    
    env.close()


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    try:
        # Run curriculum training (recommended for best results)
        train_curriculum()
        
        # Or run simple training for quick testing
        # train_simple()
        
    except KeyboardInterrupt:
        logger.warning("\nTraining interrupted by user")
        print("\nTraining interrupted. Partial model may have been saved.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed with error: {e}", exc_info=True)
        print(f"\nTraining failed: {e}")
        sys.exit(1)