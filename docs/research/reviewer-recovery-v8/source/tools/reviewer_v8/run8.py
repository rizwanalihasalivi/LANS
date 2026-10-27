"""Fixed finite recovery/expiry/query comparison; no reserved-data access."""
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
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-recovery-v8';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v8-numba',MPLCONFIGDIR='/tmp/lans-v8-mpl')
    def run(cmd,log):
        with (out/log).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    if not (out/'actors').exists():run([sys.executable,HERE/'export8.py','--run',out],'export.log')
    previous=json.loads((ROOT/'docs/research/reviewer-delay-compensation-v7/manifest.json').read_text())['hashes']
    current=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))+[f for f in (out/'actors').iterdir() if f.is_file()]
    files=current+[ROOT/n for n in previous]
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if (out/'manifest.json').exists():assert hashes==json.loads((out/'manifest.json').read_text())['hashes'],'Frozen code/model changed'
    else:
        for f in current:
            target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes),indent=2)+'\n')
    if not (out/'tests-passed.json').exists():run([sys.executable,HERE/'test8.py','-v'],'tests.log');(out/'tests-passed.json').write_text('{"passed":true,"contracts":8}\n')
    def shard(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        assert not folder.exists(),'Partial shard preserved; do not overwrite'
        run([sys.executable,HERE/'study8.py','--pair',pair,'--run',out],f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(shard,range(3)))
    if not (out/'decision.json').exists():run([sys.executable,HERE/'verify8.py','--run',out],'verification.log')
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc']
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m','Verify full recovery/expiry and compensation development matrix'],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)

if __name__=='__main__':main()
