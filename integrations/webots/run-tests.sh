#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
output=${1:-"$root/results/run-$(date -u +%Y%m%dT%H%M%SZ)"}
mkdir -p "$(dirname "$output")"
mkdir "$output" # Refuse to overwrite previous evidence.
output=$(cd "$output" && pwd)
cp "$root/config.json" "$output/config.json"
python3 - "$root" "$output" <<'PYMETA'
from pathlib import Path
import datetime, hashlib, json, platform, subprocess, sys
root, output = map(Path, sys.argv[1:])
files = ['adapter.py', 'controllers/vehicle_validation/vehicle_validation.py', 'config.json',
         'worlds/vehicle_validation.wbt', 'analyze.py', 'run-tests.sh', 'run-webots.sh',
         'install-private.sh', 'runtime-sha256.txt']
metadata = {
    'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'platform': platform.platform(), 'python': sys.version,
    'base_repository_head': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
    'webots_version': 'R2025a', 'upstream_source_commit': 'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b',
    'input_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files},
    'note': 'Input hashes identify uncommitted implementation exactly; base HEAD is not its final commit.'
}
(output / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
PYMETA
for scenario in straight left right; do
  LANS_WEBOTS_CASE=$scenario LANS_WEBOTS_OUTPUT=$output \
    timeout 120 bash "$root/run-webots.sh" --stdout --stderr --batch --mode=fast --no-rendering \
    "$root/worlds/vehicle_validation.wbt" > "$output/$scenario-console.log" 2>&1
  if [ -f "$output/failure.txt" ]; then cat "$output/failure.txt"; exit 1; fi
done
python3 "$root/analyze.py" "$output"
