#!/usr/bin/env bash
set -euo pipefail
uv pip install --python /workspace/lans-venv/bin/python eclipse-sumo==1.28.0 sumolib==1.28.0 traci==1.28.0 sumo-data==1.28.0
uv pip check --python /workspace/lans-venv/bin/python
