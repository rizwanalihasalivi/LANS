"""One command for the fixed v10 audit plus strict all-baseline claim checks."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args()
subprocess.run([sys.executable,str(ROOT/'tests/test_target20_audit.py'),'-v'],cwd=ROOT,check=True)
r=subprocess.run([sys.executable,str(ROOT/'tools/reviewer_v10/run10.py')],cwd=ROOT)
if r.returncode not in (0,2):sys.exit(r.returncode)
out=ROOT/'docs/research/reviewer-audit-v10'
subprocess.run([sys.executable,str(ROOT/'tools/controller_review/check_target20.py'),'--run',str(out)],cwd=ROOT,check=True)
if a.publish:
    files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ('.pyc','.nbc','.nbi')]
    files.extend(str(out.with_name(out.name+suffix).relative_to(ROOT)) for suffix in ('-target20.json','-initial-target20.json'))
    subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True)
    subprocess.run(['git','add','--','tools/reviewer_v10','tools/controller_review/check_target20.py','tools/controller_review/run_ppo20_audit.py','tests/test_target20_audit.py','README.md'],cwd=ROOT,check=True)
    if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','--quiet','-m','Publish active PPO audit hardened nominal rollout and twenty-percent target evidence'],cwd=ROOT,check=True)
    subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)
sys.exit(2) # Full superiority claim still needs unimplemented matched comparators/confirmation.
