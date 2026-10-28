"""Finite audit pipeline; 20% is a measured target, never a generated pass."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-audit-v10';out.mkdir(exist_ok=True,parents=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v10-numba',MPLCONFIGDIR='/tmp/lans-v10-mpl')
    def run(cmd,log):
        with (out/log).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    old=json.loads((ROOT/'docs/research/reviewer-pipeline-v9/manifest.json').read_text())['hashes']
    files=list(HERE.glob('*.py'))+[HERE/'protocol.json']+[ROOT/n for n in old]
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if (out/'manifest.json').exists():assert hashes==json.loads((out/'manifest.json').read_text())['hashes'],'Frozen audit inputs changed'
    else:
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes),indent=2)+'\n')
        for f in files[:len(list(HERE.glob('*.py')))+1]:
            target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    if not (out/'tests-passed.json').exists():
        for n,script in [('new',HERE/'test10.py'),('credit',ROOT/'tools/reviewer_v6/test6.py'),('recovery',ROOT/'tools/reviewer_v8/test8.py'),('interface',ROOT/'tools/reviewer_v9/test9.py')]:run([sys.executable,script,'-v'],f'tests-{n}.log')
        (out/'tests-passed.json').write_text('{"passed":true,"contracts":36}\n')
    if not (out/'numerics.json').exists():run([sys.executable,HERE/'numerics10.py','--output',out/'numerics.json'],'numerics.log')
    if not (out/'inventory.json').exists():run([sys.executable,HERE/'inventory10.py','--output',out/'inventory.json'],'inventory.log')
    def study(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        assert not folder.exists(),'Partial diagnostic retained; no hidden retry'
        run([sys.executable,HERE/'study10.py','--run',out,'--pair',pair],f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(study,range(3)))
    if not (out/'decision.json').exists():run([sys.executable,HERE/'verify10.py','--run',out],'verification.log')
    if not (out/'timing/summary.json').exists():
        assert not (out/'timing').exists(),'Partial timing retained'
        run([sys.executable,HERE/'timing10.py','--run',out],'timing.log')
    if not (out/'timing/full-verification.json').exists():run([sys.executable,HERE/'verify_runtime10.py','--run',out],'timing-verification.log')
    run([sys.executable,HERE/'finish10.py','--run',out],'report.log')
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ('.pyc','.nbc','.nbi')]
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True);subprocess.run(['git','add','--','tools/reviewer_v10','README.md'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','--quiet','-m','Audit active PPO path fix causal terminal and packet contracts and report twenty-percent feasibility'],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)
    print((out/'decision.json').read_text());return 2 if not json.loads((out/'decision.json').read_text())['diagnostic_twenty_percent_pass'] else 0
if __name__=='__main__':sys.exit(main())
