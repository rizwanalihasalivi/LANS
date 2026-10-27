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
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'docs/research/reviewer-followup-v2')
    p.add_argument('--publish',action='store_true');args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    files=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'requirements.txt']
    previous=json.loads((ROOT/'docs/research/reviewer-causal-v1/manifest.json').read_text())
    files += [ROOT/name for name in previous['hashes']]
    files+=list((ROOT/'tools/reviewer_campaign').glob('*.py'))+[ROOT/'tools/reviewer_campaign/protocol.json']
    for seed in (701,802,903):files+=list((ROOT/f'docs/research/causal-interface-2026-10-26/models/{seed}').glob('*'))
    for seed in (2701,2802,2903):files += [ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{seed}/policy.zip']
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()}
    manifest=out/'manifest.json'
    if manifest.exists():assert json.loads(manifest.read_text())['hashes']==hashes,'Frozen inputs changed; use a new output'
    else:
        for relative in hashes:
            target=out/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,target)
        manifest.write_text(json.dumps(dict(hashes=hashes,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()),indent=2)+'\n')
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR='/tmp/lans-followup-mpl',NUMBA_CACHE_DIR='/tmp/lans-campaign-numba')
    def call(cmd,log):
        with log.open('w') as h:subprocess.run(cmd,cwd=ROOT,env=env,stdout=h,stderr=subprocess.STDOUT,check=True)
    def publish(label):
        if not args.publish:return
        subprocess.run(['git','add','-f',str(out.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m',label],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','-c',"credential.helper=!gh auth git-credential",'push','origin',branch],cwd=ROOT,check=True)
    if not (out/'tests-passed.json').exists():
        call([sys.executable,str(HERE/'test_followup.py'),'-v'],out/'tests.log')
        (out/'tests-passed.json').write_text('{"passed":true}\n');publish('research: freeze same-gain smoothing and nominal PSF follow-up')
    def job(pair):
        folder=out/f'pair-{pair}'
        if (folder/'complete.json').exists():return
        if folder.exists():raise ValueError('Incomplete shard preserved; investigate before retry')
        call([sys.executable,str(HERE/'experiment.py'),'--pair',str(pair),'--output',str(folder)],out/f'pair-{pair}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(job,range(3)))
    call([sys.executable,str(HERE/'report.py'),'--run',str(out)],out/'verification.log')
    publish('research: verify same-gain attribution smoothing and nominal safety-filter comparison')


if __name__=='__main__':main()
