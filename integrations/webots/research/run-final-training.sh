#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${LANS_PYTHON:-/workspace/lans-setup/venv/bin/python}
output=${1:-"$root/../results/research-training"}
mkdir -p "$output"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMBA_CACHE_DIR="$root/../.runtime/numba" MPLCONFIGDIR="$root/../.runtime/mpl" XDG_CACHE_HOME="$root/../.runtime/cache"
export PYTHONDONTWRITEBYTECODE=1
pids=()
for role in full residual; do
  for seed in 0 1 2 3 4; do
    if [ -f "$output/$role-$seed/complete.json" ]; then
      "$python" - "$output/$role-$seed" <<'PYVERIFY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);m=json.loads((p/'complete.json').read_text())
assert m['steps']==1000000 and m['training_profile']=='positive_survival_v2'
assert m['policy_sha256']==hashlib.sha256((p/'policy.zip').read_bytes()).hexdigest()
print('Keeping verified completed checkpoint',p.name)
PYVERIFY
      continue
    fi
    "$python" "$root/train-v2.py" --role "$role" --seed "$seed" --output "$output/$role-$seed" > "$output/$role-$seed.log" 2>&1 &
    pids+=("$!")
    if [ "${#pids[@]}" -eq 4 ]; then
      for pid in "${pids[@]}"; do wait "$pid"; done
      pids=()
    fi
  done
done
for pid in "${pids[@]}"; do wait "$pid"; done
