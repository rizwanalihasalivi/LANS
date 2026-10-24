#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${LANS_PYTHON:-/workspace/lans-setup/venv/bin/python}
output=${1:-"$root/../results/research-training"}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMBA_CACHE_DIR="$root/../.runtime/numba" MPLCONFIGDIR="$root/../.runtime/mpl" XDG_CACHE_HOME="$root/../.runtime/cache"
export PYTHONDONTWRITEBYTECODE=1
pids=()
for seed in 0 1 2 3 4; do
  "$python" "$root/train-residual.py" --role residual --seed "$seed" --output "$output/residual-$seed" > "$output/residual-$seed.log" 2>&1 &
  pids+=("$!")
  if [ "${#pids[@]}" -eq 3 ]; then
    for pid in "${pids[@]}"; do wait "$pid"; done
    pids=()
  fi
done
for pid in "${pids[@]}"; do wait "$pid"; done
