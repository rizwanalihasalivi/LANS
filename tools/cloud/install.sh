#!/usr/bin/env bash
set -euo pipefail
export UV_PYTHON_INSTALL_DIR=/workspace/.lans-python
export UV_PYTHON_BIN_DIR=/workspace/.lans-bin
export UV_CACHE_DIR=/workspace/.uv-cache
mkdir -p "$UV_PYTHON_BIN_DIR"
uv python install 3.10
if [ ! -x /workspace/lans-venv/bin/python ]; then
    uv venv --python 3.10 /workspace/lans-venv
fi
export PATH=/workspace/lans-venv/bin:$PATH
cd /workspace/LANS
uv pip install --python /workspace/lans-venv/bin/python swig==4.4.1
uv pip install --python /workspace/lans-venv/bin/python -r requirements_fixed.txt --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
uv pip install --python /workspace/lans-venv/bin/python highway-env==1.8.2
uv pip check --python /workspace/lans-venv/bin/python
