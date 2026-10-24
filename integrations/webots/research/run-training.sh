#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${LANS_PYTHON:-/workspace/lans-setup/venv/bin/python}
output=${1:-"$root/../results/research-training"}
mkdir -p "$output"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMBA_CACHE_DIR="$root/../.runtime/numba"
export MPLCONFIGDIR="$root/../.runtime/mpl" XDG_CACHE_HOME="$root/../.runtime/cache"
export PYTHONDONTWRITEBYTECODE=1
# Three workers leave one of the four available CPU cores for simulator validation.
pids=()
for role in full residual; do
  for seed in 0 1 2 3 4; do
    trainer=train.py
    if [ "$role" = residual ]; then trainer=train-residual.py; fi
    "$python" "$root/$trainer" --role "$role" --seed "$seed" --output "$output/$role-$seed" > "$output/$role-$seed.log" 2>&1 &
    pids+=("$!")
    if [ "${#pids[@]}" -eq 3 ]; then
      for pid in "${pids[@]}"; do wait "$pid"; done
      pids=()
    fi
  done
done
for pid in "${pids[@]}"; do wait "$pid"; done
