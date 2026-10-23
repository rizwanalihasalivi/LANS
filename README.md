# LANS - Latency-Aware Neuro-Symbolic Control for Autonomous Vehicles

(https://www.python.org/)
(https://pytorch.org/)

## 📖 Table of Contents

1. [What is LANS?](#what-is-lans)
2. [Key Features](#key-features)
3. [System Requirements](#system-requirements)
4. [Software Requirements](#software-requirements)
5. [Installation Guide](#installation-guide)
6. [Project Structure](#project-structure)
7. [Quick Start](#quick-start)
8. [Step-by-Step Guide](#step-by-step-guide)
9. [Configuration Guide](#configuration-guide)
10. [Running Experiments](#running-experiments)
11. [Reproducing Figures](#reproducing-figures)
12. [Troubleshooting](#troubleshooting)
13. [Citation](#citation)
14. [License](#license)

---

## What is LANS?

LANS (Latency-Aware Neuro-Symbolic Control)** is a hybrid control framework for autonomous vehicle path tracking that combines:

- **LQR (Linear Quadratic Regulator)**: A model-based controller that provides guaranteed stability
- **PPO (Proximal Policy Optimization)**: A learning-based residual controller that corrects tracking errors
- **Adaptive Gain β(τ)**: A latency-aware mechanism that modulates neural contribution based on real-time inference latency
- **Latency-Aware Reward Function**: A reward function that penalizes computational delay

LANS achieves **4.9 kHz inference on CPU-only hardware** with **>200 ms jitter tolerance**, making it suitable for deployment on mass-producible automotive ECUs without expensive GPUs.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **CPU-only inference** | Runs entirely on CPU (no GPU required) |
| **High-speed control** | 4.9 kHz inference frequency (203 µs per cycle) |
| **Jitter robustness** | Maintains stability under >200 ms computational jitter |
| **Latency awareness** | Adaptive gain β(τ) reduces neural contribution during high latency |
| **Parameter robustness** | Handles ±33% mass variation without retuning |
| **Zero-shot generalization** | Generalizes to structurally similar unseen trajectories |
| **Energy efficient** | 305× lower energy consumption vs GPU-based DRL |

---

## System Requirements

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 1.8 GHz dual-core | 2.5 GHz quad-core |
| **RAM** | 4 GB | 8 GB or more |
| **Storage** | 5 GB free space | 10 GB free space |
| **GPU** | Not required | Not required |

### Operating System

| OS | Version | Status |
|----|---------|--------|
| **Windows** | 10 / 11 | ✅ Supported |
| **Linux** | Ubuntu 20.04+ | ✅ Supported (Recommended) |
| **macOS** | 11.0+ (Big Sur) | ✅ Supported |

---

## Software Requirements

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.10.x | Programming language |
| **pip** | Latest | Package manager |
| **Git** | Latest | Version control |
| **Conda** (optional) | Latest | Environment management |
| **VS Code** (recommended) | Latest | IDE |

---

## Installation Guide

### Option 1: Using Conda (Recommended)

#### Step 1: Install Conda

Download and install Anaconda or Miniconda:

- **Anaconda**: https://www.anaconda.com/download
- **Miniconda**: https://docs.conda.io/en/latest/miniconda.html

#### Step 2: Clone the Repository

```bash
git clone https://github.com/yourusername/lans-thesis.git
cd lans-thesis
```

#### Step 3: Create Conda Environment

```bash
conda env create -f environment.yml
```

#### Step 4: Activate Environment

```bash
conda activate lans_record_env
```

---

### Option 2: Using pip (Virtual Environment)

#### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/lans-thesis.git
cd lans-thesis
```

#### Step 2: Create Virtual Environment

**Windows:**
```bash
python -m venv lans_env
lans_record_env\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv lans_env
source lans_env/bin/activate
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Required Packages with Versions

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **numpy** | ≥1.24.0 | Numerical computing |
| **scipy** | ≥1.10.0 | Scientific computing |
| **matplotlib** | ≥3.7.0 | Plotting |
| **pandas** | ≥1.5.0 | Data analysis |
| **torch** | ≥2.0.0 | Deep learning (PPO) |
| **torchvision** | ≥0.15.0 | Vision utilities |
| **gymnasium** | ≥1.0.0 | RL environment |
| **highway-env** | ≥1.8.0 | Autonomous driving simulator |
| **osqp** | ≥0.6.0 | Quadratic programming (MPC) |
| **tqdm** | ≥4.65.0 | Progress bars |
| **pyyaml** | ≥6.0.0 | Configuration parsing |
| **seaborn** | ≥0.12.0 | Enhanced plotting |
| **jupyter** | ≥1.0.0 | Notebooks |
| **ipython** | ≥8.0.0 | Interactive Python |

### Optional Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **do-mpc** | ≥4.0.0 | Alternative MPC implementation |
| **casadi** | ≥3.6.0 | Numerical optimization |
| **tensorboard** | ≥2.12.0 | Training visualization |
| **onnxruntime** | ≥1.14.0 | Model deployment |

---

## Project Structure

```
lans-thesis/
├── README.md                           # This file
├── environment.yml                     # Conda environment
├── requirements.txt                    # pip requirements
├── LICENSE                             # MIT License
│
├── src/                                # Source code
│   ├── __init__.py
│   ├── lqr_controller.py               # LQR baseline
│   ├── ppo_agent.py                    # PPO residual policy
│   ├── latency_monitor.py              # Latency measurement
│   ├── fusion_layer.py                 # Hybrid fusion
│   ├── vehicle_model.py                # 2DOF vehicle dynamics
│   ├── reference_trajectory.py         # ISO 3888-2 trajectory
│   └── utils.py                        # Helper functions
│
├── train/                              # Training scripts
│   ├── __init__.py
│   ├── train_lans.py                   # LANS training
│   ├── train_ppo.py                    # Standard PPO training
│   ├── configs/
│   │   ├── lans_config.yaml            # LANS configuration
│   │   └── ppo_config.yaml             # PPO configuration
│   └── utils/
│       ├── reward.py                   # Reward functions
│       └── environment.py              # Environment wrapper
│
├── evaluation/                         # Evaluation scripts
│   ├── __init__.py
│   ├── evaluate.py                     # Main evaluation
│   ├── ablation_study.py               # Ablation experiments
│   ├── jitter_test.py                  # Jitter robustness test
│   ├── mass_robustness.py              # Mass variation test
│   ├── zero_shot_generalization.py     # Zero-shot test
│   ├── latency_measurement.py          # Inference latency measurement
│   ├── mpc_comparison.py               # MPC comparison
│   └── plot_results.py                 # Plot generation
│
├── notebooks/                          # Jupyter notebooks
│   ├── Figure_3_Tracking_Error.ipynb
│   ├── Figure_4_Inference_Latency.ipynb
│   ├── Figure_5_Jitter_Response.ipynb
│   ├── Figure_6_Mass_Robustness.ipynb
│   ├── Figure_7_ZeroShot_Generalization.ipynb
│   └── Figure_10_Ablation_Study.ipynb
│
├── models/                             # Trained models
│   ├── lans_policy.pth
│   ├── lans_value.pth
│   ├── ppo_policy.pth
│   └── checkpoints/
│
├── data/                               # Data files
│   ├── simulation_results.csv
│   ├── inference_times.npy
│   ├── mass_variation_results.csv
│   └── generalization_results.csv
│
├── figures/                            # Generated figures
│   ├── Figure_3_*.png
│   ├── Figure_4_*.png
│   ├── Figure_5_*.png
│   ├── Figure_6_*.png
│   ├── Figure_7_*.png
│   └── Figure_10_*.png
│
└── docker/                             # Docker support
    └── Dockerfile
```

---

## Step-by-Step Guide

### Step 1: Install Python 3.10

**Windows:**
1. Download Python 3.10 from: https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Click "Install Now"

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
```

**macOS:**
```bash
brew install python@3.10
```

---

### Step 2: Verify Python Installation

**Open Terminal/Command Prompt and run:**
```bash
python --version
```

**Expected output:** `Python 3.10.x`

---

### Step 3: Install Git

**Windows:** Download from: https://git-scm.com/download/win

**Linux:**
```bash
sudo apt install git
```

**macOS:**
```bash
brew install git
```

---

### Step 4: Clone the Repository

```bash
git clone https://github.com/yourusername/lans-thesis.git
cd lans-thesis
```

---

### Step 5: Set Up the Environment

#### Option A: Using Conda (Recommended)

```bash
conda env create -f environment.yml
conda activate lans_record_env
```

#### Option B: Using pip with Virtual Environment

**Windows:**
```bash
python -m venv lans_env
lans_env\Scripts\activate
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
python3 -m venv lans_env
source lans_env/bin/activate
pip install -r requirements.txt
```

---

### Step 6: Verify Installation

```bash
python -c "import torch; print('PyTorch:', torch.__version__)"
python -c "import highway_env; print('highway-env OK')"
python -c "import gymnasium as gym; print('gymnasium OK')"
```

---

### Step 7: Train the LANS Controller

```bash
python train/train_lans.py --config train/configs/lans_config.yaml
```

**Expected Output:**
```
============================================================
LANS TRAINING STARTED
============================================================
Config: train/configs/lans_config.yaml
Device: cpu
============================================================
Episode 1:  RMSE: 0.312 m,  Loss: 0.45
Episode 100: RMSE: 0.245 m,  Loss: 0.32
Episode 500: RMSE: 0.215 m,  Loss: 0.18
...
Episode 5000: RMSE: 0.199 m, Loss: 0.05
============================================================
TRAINING COMPLETE
============================================================
Model saved to: models/lans_policy.pth
============================================================
```

---

### Step 8: Run Evaluation

```bash
python evaluation/evaluate.py --controller lans --seeds 10
```

---

### Step 9: Generate Figures

```bash
jupyter notebook notebooks/
```

Open each notebook and run all cells to regenerate figures.

---

## Quick Start

### One-Line Setup (Linux/macOS)

```bash
git clone https://github.com/yourusername/lans-thesis.git && cd lans-thesis && conda env create -f environment.yml && conda activate lans_record_env
```

### One-Line Setup (Windows PowerShell)

```powershell
git clone https://github.com/yourusername/lans-thesis.git; cd lans-thesis; conda env create -f environment.yml; conda activate lans_record_env
```

---

## Configuration Guide

### lans_config.yaml

```yaml
# LANS Training Configuration

# Environment settings
environment:
  sim_frequency: 100        # Hz
  control_frequency: 100    # Hz
  speed: 25.0               # m/s (90 km/h)
  lane_width: 3.5           # meters
  max_steps: 500            # per episode

# LQR settings
lqr:
  Q: [100, 1, 50, 10]       # State weights
  R: 1.0                    # Control weight

# PPO settings
ppo:
  learning_rate: 3e-4
  batch_size: 64
  epochs: 10
  gamma: 0.99               # Discount factor
  lambda: 0.95              # GAE smoothing
  clip_range: 0.2
  entropy_coef: 0.01
  value_coef: 0.5
  total_timesteps: 1000000

# Latency settings
latency:
  threshold: 5.0            # ms (β(τ) starts decaying)
  scale: 20.0               # ms (decay rate)

# Reward weights
reward:
  track_weight: 1.0
  effort_weight: 0.1
  latency_weight: 0.05

# Training
training:
  episodes: 5000
  seeds: 10
  save_interval: 500
```

---

## Running Experiments

### 1. Train LANS

```bash
python train/train_lans.py --config train/configs/lans_config.yaml --seed 42
```

### 2. Train Standard PPO (Baseline)

```bash
python train/train_ppo.py --config train/configs/ppo_config.yaml --seed 42
```

### 3. Run Ablation Study

```bash
python evaluation/ablation_study.py --seeds 10 --output ablation_results.csv
```

### 4. Run Jitter Robustness Test

```bash
python evaluation/jitter_test.py --jitter 130 --seed 42
```

### 5. Run Mass Robustness Test

```bash
python evaluation/mass_robustness.py --mass_range 1100 2200 --seeds 10
```

### 6. Run Zero-Shot Generalization

```bash
python evaluation/zero_shot_generalization.py --paths sine snake sharp_step
```

### 7. Measure Inference Latency

```bash
python evaluation/latency_measurement.py --iterations 10000
```

### 8. Compare with MPC

```bash
python evaluation/mpc_comparison.py
```

---

## Reproducing Figures

### Using Jupyter Notebooks

```bash
jupyter notebook notebooks/
```

Open each notebook and run all cells (Cell → Run All).

### Using Python Scripts

```bash
python evaluation/plot_results.py --figures all
```

### Figure Generation Commands

| Figure | Command |
|--------|---------|
| Figure 3: Lateral Tracking Error | `python evaluation/plot_results.py --figure 3` |
| Figure 4: Inference Latency | `python evaluation/plot_results.py --figure 4` |
| Figure 5: Jitter Response | `python evaluation/plot_results.py --figure 5` |
| Figure 6: Mass Robustness | `python evaluation/plot_results.py --figure 6` |
| Figure 7: Zero-Shot Generalization | `python evaluation/plot_results.py --figure 7` |
| Figure 10: Ablation Study | `python evaluation/plot_results.py --figure 10` |

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: `ModuleNotFoundError: No module named 'highway_env'`

**Solution:**
```bash
pip install highway-env
```

#### Issue 2: `ModuleNotFoundError: No module named 'torch'`

**Solution:**
```bash
pip install torch torchvision
```

#### Issue 3: Conda command not found

**Solution:** Add conda to PATH or use pip instead:
```bash
pip install -r requirements.txt
```

#### Issue 4: Out of memory

**Solution:** Reduce batch size or use CPU-only:
```bash
python train/train_lans.py --config lans_config.yaml --device cpu
```

#### Issue 5: Figures not saving

**Solution:** Create figures directory:
```bash
mkdir figures
```

#### Issue 6: Permission denied

**Solution (Linux/macOS):**
```bash
chmod +x *.sh
```

Solution (Windows): Run as Administrator.

---

## Citation

If you use this code or data in your research, please contact before used:

## Contact

For questions, issues, or collaborations:

- Email: rizwanalihasalivi@njfu.eu.cn

---

 Acknowledgments

This work was supported by the College of Automotive and Traffic Engineering, Nanjing Forestry University, China.

---

 Quick Reference Card

| Command | Purpose |
|---------|---------|
| `conda activate lans_record_env` | Activate environment |
| `python train/train_lans.py` | Train LANS |
| `python evaluation/evaluate.py` | Run evaluation |
| `jupyter notebook` | Open notebooks |
| `python evaluation/plot_results.py` | Generate figures |

---

Happy Researching

---

*Last Updated: June 2026*


## Research checkpoint — 24 October 2026

The proposed PPO-dominant LANS revision, discussion decisions, historical package reviews and source uploads are recorded in the [research handoff](docs/research/README.md). Setup and simulator smoke checks are documented in [cloud setup](tools/cloud/README.md). The proposed architecture has not yet been implemented or experimentally validated; existing results belong to the earlier work.
