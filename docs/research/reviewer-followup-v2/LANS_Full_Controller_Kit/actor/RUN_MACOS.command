#!/bin/bash
# Creates a local Python environment; runs no training or vehicle commands.
set -euo pipefail
cd "$(dirname "$0")"
finish() { printf '\nPress Return to close. '; read -r _ || true; }
trap 'code=$?; if [ "$code" -ne 0 ]; then printf "\nBenchmark stopped. Please share the error above.\n"; fi; finish' EXIT
python_bin=""
for candidate in python3.11 python3.12 python3.13 python3.14 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    python_bin=$(command -v "$candidate")
    break
  fi
done
if [ -z "$python_bin" ]; then
  printf 'Python 3.11 or newer is required. Install the macOS universal2 installer from python.org, then run this file again.\n'
  exit 1
fi
if [ ! -x .venv/bin/python ]; then "$python_bin" -m venv .venv; fi
.venv/bin/python -m pip install --disable-pip-version-check --only-binary=:all: 'numpy>=1.23,<3'
result_folder="mac-results-$(date +%Y%m%d-%H%M%S)-$$"
.venv/bin/python laptop_benchmark.py --output "$result_folder" --seconds 10
printf '\nFinished. Send summary.json from %s back to this chat.\n' "$result_folder"
printf 'This measures CPU/IPC with recorded inputs, not live vehicle sensors or actuators.\n'
