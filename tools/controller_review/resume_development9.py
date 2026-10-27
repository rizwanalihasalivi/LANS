"""Preserve frozen training protocol; replay actors at their actual execution shape."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'docs/research/reviewer-pipeline-v9'
if (out/'development-evidence-hashes.json').exists():
    subprocess.run([sys.executable,str(ROOT/'tools/controller_review/seal_development9.py')],check=True);sys.exit(0)
markers=[out/f'pair-{i}/complete.json' for i in range(3)]
if not all(f.exists() for f in markers):
    result=subprocess.run([sys.executable,str(ROOT/'tools/reviewer_v9/run9.py')])
    if result.returncode and not all(f.exists() for f in markers):sys.exit(result.returncode)
# Single-row inference is an audit correction, not relaxed class agreement.
# Original source/model hashes are checked by the new full replay, unchanged.
subprocess.run([sys.executable,str(ROOT/'tools/controller_review/verify_development9.py'),'--run',str(out)],check=True)

subprocess.run([sys.executable,str(ROOT/'tools/controller_review/seal_development9.py')],check=True)
