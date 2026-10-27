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
CORE=['boot9','features9','model9','env9','train9','export9','study9','verify9','test9','runtime9','verify_laptop9','run9']

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-pipeline-v9';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v9-numba',MPLCONFIGDIR='/tmp/lans-v9-mpl')
    def run(cmd,log):
        with (out/log).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    previous=json.loads((ROOT/'docs/research/reviewer-recovery-v8/manifest.json').read_text())['hashes']
    files=[HERE/(n+'.py') for n in CORE]+[HERE/'protocol.json',ROOT/'tools/reviewer_v6/credit6.py']+[ROOT/n for n in previous]
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if (out/'manifest.json').exists():assert hashes==json.loads((out/'manifest.json').read_text())['hashes'],'Frozen model/source inputs changed'
    else:
        for f in files[:len(CORE)+2]:
            target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes),indent=2)+'\n')
    if not (out/'tests-passed.json').exists():run([sys.executable,HERE/'test9.py','-v'],'tests.log');(out/'tests-passed.json').write_text('{"contracts":8,"passed":true}\n')
    def train(job):
        arm,pair=job;folder=out/f'{arm}-{pair}'
        if (folder/'complete.json').exists():return
        assert not folder.exists(),'Partial training preserved; no hidden retry'
        run([sys.executable,HERE/'train9.py','--arm',arm,'--pair',pair,'--output',folder],f'{arm}-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(train,[(arm,pair) for pair in range(3) for arm in ('legacy_history','causal_history')]))
    if not (out/'actors/manifest.json').exists():
        assert not (out/'actors').exists(),'Partial model export retained'
        run([sys.executable,HERE/'export9.py','--run',out],'export.log')
    def evaluate(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        assert not folder.exists(),'Partial evaluation retained'
        run([sys.executable,HERE/'study9.py','--run',out,'--pair',pair],f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(evaluate,range(3)))
    if not (out/'decision.json').exists():run([sys.executable,HERE/'verify9.py','--run',out],'verification.log')
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc']
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','--quiet','-m','Verify finite causal-state matched retraining and frozen comparison'],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)

if __name__=='__main__':main()
