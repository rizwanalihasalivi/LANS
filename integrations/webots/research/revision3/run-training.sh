#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${LANS_PYTHON:-"$root/../../.runtime/research-venv/bin/python"}
output=${1:-"$root/../../results/revision3-training"}
selection=${2:-"$root/../../results/revision3-extended/user-selection.json"}
candidate=$("$python" -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d.get("full_training_user_approved") is True, "Full training waits for the user-approved extended-pilot decision"; print(d["selected_candidate"])' "$selection")
mkdir -p "$output"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMBA_CACHE_DIR="$root/../../.runtime/numba" MPLCONFIGDIR="$root/../../.runtime/mpl" XDG_CACHE_HOME="$root/../../.runtime/cache"
export PYTHONDONTWRITEBYTECODE=1
pids=()
for seed in 0 1 2 3 4; do
  "$python" "$root/train.py" --candidate "$candidate" --selection "$selection" --steps 1000000 --seed "$seed" --output "$output/residual-$seed" > "$output/residual-$seed.log" 2>&1 &
  pids+=("$!")
  if [ "${#pids[@]}" -eq 4 ]; then
    for pid in "${pids[@]}"; do wait "$pid"; done
    pids=()
  fi
done
for pid in "${pids[@]}"; do wait "$pid"; done
