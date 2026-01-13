# Thesis Outline: Transfer Learning–Enhanced DRL for Path and Trajectory Tracking

## Chapter 1: Introduction
Motivation, research gap: many DRL controllers are trained for fixed conditions; transfer learning can reduce retraining time when vehicle speed/curvature or environment changes. State the contributions: (1) robust LQR baseline, (2) PPO-based DRL controller, (3) transfer-learning methods for fast adaptation, (4) empirical comparison.

## Chapter 2: Literature Review
Survey vehicle control (LQR, MPC), DRL for autonomous driving (DDPG, PPO, SAC), and transfer learning in RL and control. Include discussion of Ashwin & Raj (2023) DDPG lane-keeping/overtaking and other related works.

## Chapter 3: Vehicle Modeling and Baseline Controller
Derive the 2-DOF bicycle model, linearization, tracking-error formulation, LQR design (continuous vs discrete), path generation (double-lane-change ISO 3888-2), numerical integration choices, and baseline results.

## Chapter 4: DRL Controller Design
Gymnasium environment details, state/action/reward design, PPO architecture, training pipeline, and hyperparameters.

## Chapter 5: Transfer Learning Methodology
Describe parameter transfer, layer freezing, fine-tuning strategies, and experimental setup for source/target tasks (different speeds, curvatures). Include rationale for progressive unfreezing and learning rate scheduling.

## Chapter 6: Experiments and Results
Experimental protocol, performance metrics (RMSE lateral, max lateral, IAE, steering effort, saturation), comparison LQR vs PPO vs transfer-PPO, ablation studies on freezing strategy, and sample complexity plots.

## Chapter 7: Discussion and Limitations
Interpret results, discuss when transfer helps/hurts, limitations of linear model vs full dynamics, sensor noise and domain randomization considerations.

## Chapter 8: Conclusion and Future Work
Summarize findings and propose extensions: sim-to-real, richer vehicle models (nonlinear), curriculum learning, and online adaptation.

## References
- Ashwin & Raj (2023). Title TBD. DDPG for lane-keeping/overtaking.
- Sutton & Barto. Reinforcement Learning: An Introduction.
- Schulman et al. Proximal Policy Optimization Algorithms.
- Typical vehicle dynamics references for 2-DOF bicycle model.
