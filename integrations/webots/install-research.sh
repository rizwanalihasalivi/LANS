#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export UV_CACHE_DIR="$root/.runtime/uv-cache"
export UV_PYTHON_INSTALL_DIR="$root/.runtime/python"
export UV_PYTHON_BIN_DIR="$root/.runtime/bin"
mkdir -p "$UV_CACHE_DIR" "$UV_PYTHON_BIN_DIR"
uv python install 3.10.22
if [ ! -x "$root/.runtime/research-venv/bin/python" ]; then
  uv venv --python "$UV_PYTHON_INSTALL_DIR/cpython-3.10-linux-x86_64-gnu/bin/python3.10" "$root/.runtime/research-venv"
fi
python="$root/.runtime/research-venv/bin/python"
uv pip install --python "$python" 'torch==2.0.0+cpu' --index-url https://download.pytorch.org/whl/cpu
uv pip install --python "$python" numpy==1.23.5 scipy==1.10.1 matplotlib==3.7.1 pandas==2.0.0 pillow==9.5.0 \
  stable-baselines3==2.0.0 gymnasium==0.28.1 numba==0.57.1
uv pip check --python "$python"
