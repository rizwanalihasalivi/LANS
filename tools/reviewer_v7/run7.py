import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-delay-compensation-v7';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v7-numba',MPLCONFIGDIR='/tmp/lans-v7-mpl')
    def run(cmd,log):
        with (out/log).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    actor=out/'actor'
    if not actor.exists():
        original=ROOT/'docs/research/reviewer-history-v5/portable-actor';shutil.copytree(original,actor)
        m=json.loads((actor/'manifest.json').read_text());m['profile']='latency_compensated_query_v7';m['adaptation']=dict(original_profile='causal_filter_history_v5',weights_unchanged=True,new_training_steps=0,
            scope='Diagnostic input forecast adapter; pretrained policy not retrained on forecast-state distribution')
        (actor/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    files=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))+[ROOT/'tools/controller_review'/n for n in ('laptop_full_controller.py','verify_full_laptop.py','verify_runtime7.py')]+[f for f in actor.iterdir() if f.is_file()]
    previous=json.loads((ROOT/'docs/research/reviewer-history-v5/manifest.json').read_text())['hashes']
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files+[ROOT/n for n in previous]}
    if (out/'manifest.json').exists():assert hashes==json.loads((out/'manifest.json').read_text())['hashes'],'Frozen source changed'
    else:
        for f in files:
            target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes),indent=2)+'\n')
    if not (out/'tests-passed.json').exists():run([sys.executable,HERE/'test7.py','-v'],'tests.log');(out/'tests-passed.json').write_text('{"passed":true,"contracts":8}\n')
    if not (out/'generated.json').exists():run([sys.executable,HERE/'study7.py','--run',out],'study.log')
    if not (out/'verification.json').exists():run([sys.executable,HERE/'verify7.py','--run',out],'verification.log')
    for seed in (701,802,903):
        folder=out/'runtime'/f'seed-{seed}'
        if not (folder/'summary.json').exists():
            assert not folder.exists(),'Partial runtime evidence retained'
            folder.parent.mkdir(exist_ok=True)
            run([sys.executable,ROOT/'tools/controller_review/laptop_full_controller.py','--models',actor,'--profile','delay_compensated','--seed',seed,'--seconds','1','--output',folder],f'runtime-{seed}.log')
    if not (out/'runtime-verification.json').exists():run([sys.executable,ROOT/'tools/controller_review/verify_runtime7.py','--run',out],'runtime-verification.log')
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and not any(x in f.parts for x in ('__pycache__','.numba-cache')) and f.suffix!='.pyc']
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m','Verify explicit response-delay input compensation and retain matched outcomes'],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)

if __name__=='__main__':main()
