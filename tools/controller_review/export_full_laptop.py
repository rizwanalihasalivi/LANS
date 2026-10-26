"""Create a repository-shaped, Torch-free Python3.10/3.11 SIL laptop bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[2]
FILES='''tools/controller_review/laptop_full_controller.py
tools/controller_review/verify_full_laptop.py
tools/controller_review/realtime_kernels.py
tools/laptop/laptop_benchmark.py
tools/laptop/precision_wait.py
tools/reviewer_followup/boot.py
tools/reviewer_followup/filtered.py
tools/reviewer_followup/protocol.json
tools/reviewer_campaign/common.py
tools/reviewer_campaign/supervisor.py
tools/reviewer_campaign/environment.py
tools/reviewer_campaign/protocol.json
integrations/webots/research/core.py
integrations/webots/research/protocol.json
integrations/webots/research/comparison.py
integrations/webots/research/comparison-protocol.json
integrations/webots/research/revision2/plant.py
integrations/webots/research/revision2/gating.py
integrations/webots/research/revision7/kernels.py
integrations/webots/research/revision8/bootstrap.py
integrations/webots/research/revision9/bootstrap.py'''.splitlines()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    for name in FILES:
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    shutil.copytree(ROOT/'docs/research/reviewer-causal-v1/laptop-kit',out/'actor')
    (out/'requirements.txt').write_text('numpy==1.23.5\nscipy==1.10.1\nnumba==0.57.1\ngymnasium==0.28.1\n')
    (out/'RUN_WINDOWS.cmd').write_text('@echo off\ncd /d "%~dp0"\npy -3.10 -m venv .venv\nif errorlevel 1 exit /b 1\n.venv\\Scripts\\python.exe -m pip install -r requirements.txt\nif errorlevel 1 exit /b 1\n.venv\\Scripts\\python.exe tools\\controller_review\\laptop_full_controller.py --output laptop-results\npause\n')
    (out/'RUN_MAC.command').write_text('#!/bin/bash\nset -e\ncd "$(dirname "$0")"\npython3.10 -m venv .venv\n.venv/bin/python -m pip install -r requirements.txt\n.venv/bin/python tools/controller_review/laptop_full_controller.py --output laptop-results\n')
    (out/'README.md').write_text('''# LANS full-controller laptop SIL kit

Requires CPython3.10 (3.11 also supports these dependencies), internet for first dependency installation, and an extracted writable folder. No Webots, GPU or Torch required. Do not run from inside the ZIP.

Windows: double-click RUN_WINDOWS.cmd. Or in PowerShell: `py -3.10 -m venv .venv`, then `.venv\\Scripts\\python.exe -m pip install -r requirements.txt`, then `.venv\\Scripts\\python.exe tools\\controller_review\\laptop_full_controller.py --output laptop-results`.

macOS: in Terminal, run `bash RUN_MAC.command` with Python3.10 installed. Apple Silicon installation of older dependency wheels may require an appropriate Python distribution; do not silently substitute dependency versions.

Five cases run13seconds each, after untimed JIT/model warmup. Close unrelated applications and use power supply. Do not adjust system-wide priorities. Output folder must be new; use `--output laptop-results-2` for another run. Send laptop-results/Results.zip after completion. It contains timing/plant CSVs and summary; no device identifiers are requested.

To independently replay raw outputs, run the same virtual-environment Python with `tools/controller_review/verify_full_laptop.py --run laptop-results --models actor`. This verifies original deadlines, actor outputs, fallback and plant/observer/LQR replay; it does not convert timing failures into passes.

Scope: causal noisy observer, scheduled LQR, fixed age_filtered residual supervisor, NumPy PPO actor in a separate process, real IPC and original timestamps, physical steering saturation/rate dynamics in a FIXED-STEP SOFTWARE PLANT. Tests nominal,20ms/1000ms post-inference worker service delays, CPU contention and worker crash. Injected service delays are distinct from measured inference time. This is a development diagnostic, not a selected research winner or native Webots validation.

Any missed original10ms deadline fails observed strict timing; deadline misses revoke assistance, and stale/failed workers use fresh-state LQR. Functional success does not imply timing success. Fixed-step plant survival cannot establish continuous-time safety during host stalls, hard real-time guarantees, sensor/CAN/actuator timing, or real-vehicle readiness. Actual Windows/macOS results must be collected on your laptop; cloud smoke checks cannot replace them.
''')
    hashes={str(f.relative_to(out)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in out.rglob('*') if f.is_file()}
    (out/'bundle-manifest.json').write_text(json.dumps(dict(sha256=hashes,scope='software-in-loop only; actual target execution pending'),indent=2)+'\n')
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob('*'):
            if f.is_file():z.write(f,str(Path(out.name)/f.relative_to(out)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(archive,archive.stat().st_size)


if __name__=='__main__':main()
