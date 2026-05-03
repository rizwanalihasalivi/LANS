#!/bin/bash
# setup_environment.sh - Complete environment setup

echo "========================================="
echo "LANS Thesis - Environment Setup"
echo "========================================="

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv lans_env

# Activate environment
source lans_env/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing dependencies..."
pip install -r requirements_fixed.txt

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p models
mkdir -p results
mkdir -p results/statistical
mkdir -p results/figures
mkdir -p results/ablation
mkdir -p results/baselines
mkdir -p logs
mkdir -p data

# Test installation
echo "🧪 Testing installation..."
python -c "
import numpy as np
import matplotlib.pyplot as plt
import stable_baselines3 as sb3
print('✅ NumPy version:', np.__version__)
print('✅ Stable-Baselines3 version:', sb3.__version__)
print('✅ All imports successful!')
"

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "To activate environment:"
echo "  source lans_env/bin/activate"
echo ""
echo "To run experiments:"
echo "  python run_experiment_suite.py"
echo ""