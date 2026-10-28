"""Single-command recovery follow-up, exact resume, finite retest and publication."""
import boot13
import argparse
import concurrent.futures
import fcntl
import json
import os
import subprocess
import sys
import torch
import numpy as np
from checkpoint12 import atomic_json,digest,verify

ROOT,HERE=boot13.ROOT,boot13.HERE
OUT=ROOT/'docs/research/recovered-ppo-v13'


def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--verify-only',action='store_true');p.add_argument('--replay',action='store_true');args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    lock=(OUT/'run.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    protocol=json.loads((HERE/'protocol.json').read_text())
    old=ROOT/'docs/research/reviewer-followup-v2/manifest.json'
    pinned=subprocess.check_output(['git','show',protocol['parent_commit']+':'+str(old.relative_to(ROOT))],cwd=ROOT)
    assert pinned==old.read_bytes(),'Historical manifest changed'
    inputs=dict(json.loads(pinned)['hashes'])
    for name,expected in inputs.items():assert digest(ROOT/name)==expected,name
    # All tracked Python research/plant dependencies plus explicit JSON protocols.
    tracked=subprocess.check_output(['git','ls-files','tools','integrations'],cwd=ROOT,text=True).splitlines()
    for name in tracked:
        f=ROOT/name
        if f.is_file() and (f.suffix=='.py' or f.name=='protocol.json'):inputs[name]=digest(f)
    for f in HERE.iterdir():
        if f.is_file():inputs[str(f.relative_to(ROOT))]=digest(f)
    for seed in (2701,2802,2903):
        for name in ('policy.zip','reward-normalization.pkl'):
            f=ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{seed}/{name}';inputs[str(f.relative_to(ROOT))]=digest(f)
    manifest=dict(inputs=inputs,python=sys.version,numpy=np.__version__,torch=torch.__version__,sb3=__import__('stable_baselines3').__version__)
    frozen=OUT/'manifest.json'
    if frozen.exists():assert json.loads(frozen.read_text())==manifest,'Frozen source/model/environment changed'
    else:atomic_json(frozen,manifest)
    signature=digest(frozen)
    seal=OUT/'evidence-hashes.json'
    if seal.exists():
        for name,expected in json.loads(seal.read_text())['sha256'].items():assert digest(OUT/name)==expected,name
    if args.verify_only:
        assert seal.exists(),'Experiment incomplete';print('All frozen inputs and sealed evidence verified');return
    def publish(message):
        if not args.publish:return
        files=[str(f.relative_to(ROOT)) for folder in (HERE,OUT) for f in folder.rglob('*') if f.is_file()
            and '__pycache__' not in f.parts and '.partial-' not in str(f) and '.tmp-' not in str(f)
            and f.suffix not in ('.pyc','.nbc','.nbi','.lock')
            and (f.suffix!='.log' or f.name.startswith('contracts') or f.name=='recovery.log')]
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','--quiet','-m',message],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)
    def status(stage,state='running'):
        atomic_json(OUT/'status.json',dict(stage=stage,state=state,signature=signature,resume='python tools/reviewer_v13/run13.py --publish'))
    def run(script,log,*argv):
        with (OUT/log).open('w') as f:subprocess.run([sys.executable,str(script),*map(str,argv)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    if not (OUT/'contracts-passed.json').exists():
        status('contracts');run(HERE/'test13.py','contracts.log','-v')
        run(ROOT/'tools/reviewer_v6/test6.py','contracts-credit.log','-v')
        atomic_json(OUT/'contracts-passed.json',dict(passed=True,suites=['v13-physical-rate-bridge-resume','v6-submitted-credit'],logs={n:digest(OUT/n) for n in ('contracts.log','contracts-credit.log')}))
    if not (OUT/'recovered.json').exists():run(HERE/'recover13.py','recovery.log')
    publish('Freeze recovered PPO diagnosis, tested fixes and matched v13 protocol')
    from train13 import train
    for arm in protocol['training']['arms']:
        for pair in range(3):
            status(f'training:{arm}:{pair}');train(pair,arm,OUT/f'{arm}-{pair}',signature,publish)
            publish(f'Complete recovered PPO v13 {arm} pair {pair} endpoint')
    if not (OUT/'actors/final-manifest.json').exists():
        status('export');from models13 import export
        from stable_baselines3 import PPO
        for arm in protocol['training']['arms']:
            for pair in range(3):
                folder=OUT/f'{arm}-{pair}/checkpoints';pointer=json.loads((folder/'latest.json').read_text());snapshot=folder/pointer['folder'];verify(snapshot,signature)
                with (snapshot/'model.zip').open('rb') as f:model=PPO.load(f,device='cpu')
                np.savez_compressed(OUT/f'actors/{arm}-{pair}.npz',**export(model,bridge=False))
        atomic_json(OUT/'actors/final-manifest.json',dict(sha256={f.name:digest(f) for f in (OUT/'actors').glob('*.npz')}))
        publish('Export six complete recovered PPO v13 continuations')
    status('matched-development')
    def evaluate(pair):
        # Revisit complete episodes to verify each trace hash even on resume.
        run(HERE/'study13.py',f'pair-{pair}.log','--out',OUT,'--pair',pair);return pair
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in concurrent.futures.as_completed([pool.submit(evaluate,pair) for pair in range(3)]):
            publish(f'Save recovered PPO v13 matched development group {future.result()}')
    if args.replay or not (OUT/'decision.json').exists():
        status('full-replay');run(HERE/'verify13.py','verification.log','--out',OUT)
    from report13 import main as report
    report(OUT)
    evidence={str(f.relative_to(OUT)):digest(f) for f in OUT.rglob('*') if f.is_file()
        and f.name not in ('evidence-hashes.json','status.json','RESUME.md','run.lock')
        and f.suffix!='.lock' and (f.suffix!='.log' or f.name.startswith('contracts') or f.name=='recovery.log')
        and '.partial-' not in str(f) and '.tmp-' not in str(f)}
    atomic_json(seal,dict(sha256=evidence));status('complete','complete')
    (OUT/'RESUME.md').write_text('# Recovered PPO v13 experiment complete\n\nRead README.md for findings and failed/passed criteria.\n\nResume/check: `python tools/reviewer_v13/run13.py --publish`\n\nFull exact training state saved every10k steps. Six final100k endpoints only; no automatic extra training. Each completed episode has a verified trace hash. `--verify-only` checks sealed evidence; `--replay` repeats raw checks. Reserved evaluation unchanged.\n')
    publish('Publish independently replayed recovered PPO diagnosis and complete v13 outcomes')
    print((OUT/'decision.json').read_text())


if __name__=='__main__':main()
