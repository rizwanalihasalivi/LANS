"""Resume finite credit research, serialized timing and verified evidence report."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-credit-v6'
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v6-numba',MPLCONFIGDIR='/tmp/lans-v6-mpl')
    def run(*cmd):subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,check=True)
    if not (out/'decision.json').exists():run(sys.executable,ROOT/'tools/reviewer_v6/run6.py')
    decision=json.loads((out/'decision.json').read_text())
    models=ROOT/'docs/research/reviewer-history-v5/portable-actor'
    if decision['selected'] is not None:
        models=out/'selected-portable-actor'
        if not models.exists():run(sys.executable,ROOT/'tools/controller_review/export_credit6.py','--run',out,'--arm',decision['selected'],'--output',models)
    timing=out/'timing'
    if not (timing/'summary.json').exists():
        assert not timing.exists(),'Partial timing retained: inspect it; do not overwrite or retry away misses'
        run(sys.executable,ROOT/'tools/controller_review/timing_credit6.py','--output',timing,'--models',models)
    run(sys.executable,ROOT/'tools/controller_review/verify_timing_credit6.py','--run',timing)
    if not (out/'failure-diagnosis.json').exists():run(sys.executable,ROOT/'tools/controller_review/diagnose_failures6.py','--output',out)
    robust=out/'robust-scalar-contract'
    if not (robust/'summary.json').exists():
        assert not robust.exists(),'Partial contract data preserved'
        run(sys.executable,ROOT/'tools/controller_review/robust_psf_contract6.py','--output',robust)
    run(sys.executable,ROOT/'tools/controller_review/verify_robust_psf_contract6.py','--run',robust)
    assert (out/'bibliography-audit.json').exists(),'Provide the supplied manuscript to audit_bibliography6.py; do not fabricate missing primary metadata'
    run(sys.executable,ROOT/'tools/controller_review/analyze_credit6.py','--run',out)
    run(sys.executable,ROOT/'tools/controller_review/finish_credit6.py','--run',out)
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and not any(x in f.parts for x in ('__pycache__','.numba-cache','.matplotlib-cache')) and f.suffix!='.pyc']
        run('git','add','-f','--',*files)
        run('git','-c','core.whitespace=cr-at-eol','diff','--cached','--check')
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:run('git','commit','-m','Record independently verified credit intervention and original-target timing')
        push=subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT)
        if push.returncode:print('Remote push failed; local commits and verified evidence remain available. Restore GitHub credentials and push the branch. No evidence is relabeled as remotely published.',flush=True)

if __name__=='__main__':main()
