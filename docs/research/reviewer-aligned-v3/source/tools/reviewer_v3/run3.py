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
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');args=p.parse_args()
    out=ROOT/'docs/research/reviewer-aligned-v3';out.mkdir(parents=True,exist_ok=True)
    files=list(HERE.glob('*.py'))+[HERE/'protocol.json']
    previous=json.loads((ROOT/'docs/research/reviewer-followup-v2/manifest.json').read_text())['hashes']
    files+=[ROOT/n for n in previous]
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if (out/'manifest.json').exists():assert json.loads((out/'manifest.json').read_text())['hashes']==hashes,'Frozen source changed'
    else:
        for n in hashes:
            target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,target)
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes),indent=2)+'\n')
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-aligned-numba')
    def call(cmd,log):
        with log.open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    def publish(message):
        if not args.publish:return
        subprocess.run(['git','add','-f',str(out.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m',message],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin',branch],cwd=ROOT,check=True)
    if not (out/'tests-passed.json').exists():
        call([sys.executable,HERE/'test3.py','-v'],out/'tests.log');(out/'tests-passed.json').write_text('{"passed":true}\n')
        publish('research: freeze execution-aligned predictive PPO experiment')
    def train(pair):
        folder=out/f'training-{pair}'
        if (folder/'complete.json').exists():return
        if folder.exists():raise RuntimeError('Incomplete training preserved; investigate before retry')
        call([sys.executable,HERE/'train3.py','--pair',pair,'--output',folder],out/f'training-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(train,range(3)))
    publish('research: preserve all execution-aligned PPO pilot endpoints')
    def evaluate(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        if folder.exists():raise RuntimeError('Incomplete development shard preserved; investigate before retry')
        call([sys.executable,HERE/'evaluate3.py','--pair',pair,'--run',out],out/f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(evaluate,range(3)))
    call([sys.executable,HERE/'verify3.py','--run',out],out/'verification.log')
    publish('research: independently verify execution-aligned PPO development screen')
    timing=out/'timing'
    if not (timing/'dedicated_spin/summary.json').exists():
        if timing.exists():raise RuntimeError('Incomplete timing preserved; inspect before retry')
        call([sys.executable,HERE/'timing3.py','--output',timing],out/'timing.log')
    for profile in ('absolute_100us','dedicated_spin'):
        call([sys.executable,ROOT/'tools/controller_review/verify_realtime_optimized.py','--run',timing/profile,
              '--model-root',ROOT/'docs/research/reviewer-causal-v1/export'],out/f'{profile}-verification.log')
    call([sys.executable,HERE/'finish3.py','--run',out],out/'report-export.log')
    publish('research: publish timing diagnosis and execution-aligned experiment outcome')


if __name__=='__main__':main()
