#!/bin/bash
set -e
cd "$(dirname "$0")"
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/controller_review/laptop_campaign9.py --profile history_comp --budget-guard --output laptop-results
