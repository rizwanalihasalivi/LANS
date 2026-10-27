"""Resume fixed v8 work; never retry away failures or fabricate target results."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--kit-python',default=sys.executable);a=p.parse_args();out=ROOT/'docs/research/reviewer-recovery-v8'
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v8-numba',MPLCONFIGDIR='/tmp/lans-v8-mpl')
    def run(*cmd):subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,check=True)
    if (out/'evidence-hashes.json').exists():run(sys.executable,ROOT/'tools/controller_review/verify_cache8.py','--run',out)
    if not (out/'decision.json').exists():run(sys.executable,ROOT/'tools/reviewer_v8/run8.py')
    if not (out/'timing/summary.json').exists():
        assert not (out/'timing').exists(),'Partial timing retained'
        run(sys.executable,ROOT/'tools/controller_review/timing8.py','--run',out)
    if not (out/'timing/verification.json').exists():run(sys.executable,ROOT/'tools/controller_review/verify_timing8.py','--run',out)
    dynamic=out/'dynamic-recovery'
    if not (dynamic/'summary.json').exists():
        assert not dynamic.exists(),'Partial dynamic recovery retained'
        run(sys.executable,ROOT/'tools/controller_review/recovery_dynamic8.py','--output',dynamic)
    if not (dynamic/'verification.json').exists():run(sys.executable,ROOT/'tools/controller_review/verify_dynamic8.py','--run',dynamic)
    kit=out/'LANS_Recovery_Python310_Kit'
    if not kit.exists():run(sys.executable,ROOT/'tools/controller_review/export_recovery_kit8.py','--run',out)
    smoke=out/'kit-smoke'
    if not (smoke/'summary.json').exists():
        assert not smoke.exists(),'Partial smoke retained'
        run(a.kit_python,kit/'tools/controller_review/laptop_campaign6.py','--profile','recovery_compensated','--budget-guard','--models',kit/'actor','--seconds','.5','--output',smoke)
    run(sys.executable,ROOT/'tools/controller_review/verify_cache8.py','--run',out,'--seal')
    run(sys.executable,ROOT/'tools/controller_review/finish_recovery8.py','--run',out)
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and not any(x in f.parts for x in ('__pycache__','.numba-cache','.matplotlib-cache')) and f.suffix!='.pyc']
        run('git','add','-f','--',*files)
        run('git','-c','core.whitespace=cr-at-eol','diff','--cached','--check','--','.',':(exclude)docs/research/reviewer-recovery-v8/LANS_Recovery_Python310_Kit/tools/controller_review/realtime_kernels.py')
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:run('git','commit','--quiet','-m','Preserve verified recovery expiry prediction and deadline guard outcomes')
        run('git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26')

if __name__=='__main__':main()
