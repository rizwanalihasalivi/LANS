"""Actual finite corrected-PPO training, matched full development and raw replay."""
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
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-training-v11';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v11-numba',MPLCONFIGDIR='/tmp/lans-v11-mpl',XDG_CACHE_HOME='/tmp/lans-v11-cache')
    Path(env['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    def run(cmd,log):
        with (out/log).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    previous=ROOT/'docs/research/reviewer-pipeline-v9'
    frozen=subprocess.check_output(['git','show','5f80922:docs/research/reviewer-pipeline-v9/evidence-hashes.json'],cwd=ROOT)
    assert frozen==(previous/'evidence-hashes.json').read_bytes();expected=json.loads(frozen)['sha256']
    models=[]
    for pair,seed in enumerate((701,802,903)):
        for name in (f'actors/student-{seed}.npz',f'actors/causal_history-{seed}.npz',f'causal_history-{pair}/policy.zip',f'causal_history-{pair}/reward-normalization.pkl'):
            file=previous/name;assert hashlib.sha256(file.read_bytes()).hexdigest()==expected[name],name;models.append(file)
    old=json.loads((ROOT/'docs/research/reviewer-audit-v10/manifest.json').read_text())['hashes']
    files=list(HERE.glob('*.py'))+[HERE/'protocol.json']+[ROOT/n for n in old]+models
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if (out/'manifest.json').exists():assert hashes==json.loads((out/'manifest.json').read_text())['hashes'],'Frozen training/source inputs changed'
    else:
        (out/'manifest.json').write_text(json.dumps(dict(hashes=hashes,prior_seal_sha256=hashlib.sha256(frozen).hexdigest()),indent=2)+'\n')
        for f in HERE.iterdir():
            if f.is_file():target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    if not (out/'tests-passed.json').exists():
        run([sys.executable,HERE/'test11.py','-v'],'tests.log')
        run([sys.executable,ROOT/'tools/reviewer_v10/test10.py','-v'],'regression-terminal-packets.log')
        run([sys.executable,ROOT/'tools/reviewer_v6/test6.py','-v'],'regression-credit.log')
        (out/'tests-passed.json').write_text('{"passed":true,"contracts":23}\n')
    def train(pair):
        folder=out/f'training-{pair}'
        if (folder/'complete.json').exists():return
        assert not folder.exists(),'Partial training retained; no silent retry'
        run([sys.executable,HERE/'train11.py','--pair',pair,'--output',folder],f'training-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(train,range(3)))
    if not (out/'actors/manifest.json').exists():
        assert not (out/'actors').exists(),'Partial export retained'
        run([sys.executable,HERE/'export11.py','--run',out],'export.log')
    def evaluate(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        assert not folder.exists(),'Partial comparison retained'
        run([sys.executable,HERE/'study11.py','--run',out,'--pair',pair],f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(evaluate,range(3)))
    if not (out/'decision.json').exists():run([sys.executable,HERE/'verify11.py','--run',out],'verification.log')
    decision=json.loads((out/'decision.json').read_text())
    if decision['twenty_percent_development_pass']:
        if not (out/'timing/summary.json').exists():
            assert not (out/'timing').exists(),'Partial timing retained'
            run([sys.executable,HERE/'timing11.py','--run',out],'timing.log')
        if not (out/'timing/full-verification.json').exists():run([sys.executable,HERE/'verify_runtime11.py','--run',out],'timing-verification.log')
    run([sys.executable,HERE/'finish11.py','--run',out],'report.log')
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ('.pyc','.nbc','.nbi')]
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True);subprocess.run(['git','add','--','tools/reviewer_v11','README.md'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','--quiet','-m','Publish new corrected PPO training endpoints matched full comparison and verified outcomes'],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)
    print(json.dumps(decision,indent=2));return 0 if decision['twenty_percent_development_pass'] else 2
if __name__=='__main__':sys.exit(main())
