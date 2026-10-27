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
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');args=p.parse_args();out=ROOT/'docs/research/reviewer-credit-v6';out.mkdir(parents=True,exist_ok=True)
    files=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))
    previous=json.loads((ROOT/'docs/research/reviewer-history-v5/manifest.json').read_text())['hashes']
    files+=[ROOT/n for n in previous]
    for pair in range(3):files+=[ROOT/f'docs/research/reviewer-history-v5/nohistory-{pair}/policy.zip']
    for pair in range(3):files+=[ROOT/f'docs/research/reviewer-aligned-v3/training-{pair}/{n}' for n in ('policy.zip','complete.json')]
    for seed in (701,802,903):files+=[ROOT/f'docs/research/reviewer-aligned-v3/export/{seed}/{n}' for n in ('student.pt','normalization.npz','complete.json')]
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if (out/'manifest.json').exists():assert json.loads((out/'manifest.json').read_text())['hashes']==hashes,'Frozen inputs changed'
    else:
        for n in hashes:
            target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,target)
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes),indent=2)+'\n')
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v4-numba')
    def call(cmd,log):
        with log.open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    def publish(label):
        if not args.publish:return
        subprocess.run(['git','add','-f',str(out.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m',label],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin',branch],cwd=ROOT,check=True)
    if not (out/'tests-passed.json').exists():
        call([sys.executable,HERE/'test6.py','-v'],out/'tests.log');(out/'tests-passed.json').write_text('{"passed":true}\n')
        publish('research: freeze submitted-action credit and matched learning ablation')
    def train(job):
        arm,pair=job;folder=out/f'{arm}-{pair}'
        if (folder/'complete.json').exists():return
        if folder.exists():raise RuntimeError('Partial training preserved; inspect before retry')
        call([sys.executable,HERE/'train6.py','--pair',pair,'--arm',arm,'--output',folder],out/f'{arm}-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(train,[(arm,pair) for pair in range(3) for arm in ('all_actions','submitted_only')]))
    publish('research: preserve all versioned-history ablation pilot endpoints')
    def evaluate(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        if folder.exists():raise RuntimeError('Partial shard preserved; inspect before retry')
        call([sys.executable,HERE/'evaluate6.py','--pair',pair,'--run',out],out/f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(evaluate,range(3)))
    call([sys.executable,HERE/'verify6.py','--run',out],out/'verification.log')
    publish('research: verify versioned-history learning comparison and all causal transitions')


if __name__=='__main__':main()
