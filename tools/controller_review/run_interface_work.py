"""Resume fixed finite diagnoses, independent timing/recovery audits and exports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--smoke-python',default=sys.executable);args=p.parse_args()
    out=ROOT/'docs/research/reviewer-interface-v4';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v4-numba',MPLCONFIGDIR='/tmp/lans-v4-mpl',XDG_CACHE_HOME='/tmp/lans-v4-cache')
    Path(env['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    def run(cmd,log,cwd=ROOT):
        with log.open('w') as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    def publish(message):
        if not args.publish:return
        subprocess.run(['git','add','-f',str(out.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m',message],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin',branch],cwd=ROOT,check=True)
    if not (out/'decision.json').exists():run([sys.executable,ROOT/'tools/reviewer_v4/run4.py']+(['--publish'] if args.publish else []),out/'resume-development.log')
    if not (out/'deep-analysis.json').exists():run([sys.executable,HERE/'analyze_open_issues.py','--output',out/'deep-analysis.json'],out/'deep-analysis.log')
    for name,script,verifier in (('timing','timing_interface4.py','verify_timing_interface4.py'),('recovery','recovery_interface4.py','verify_recovery_interface4.py')):
        folder=out/name
        if not (folder/'summary.json').exists():
            if folder.exists():raise RuntimeError('Partial '+name+' preserved; inspect before retry')
            run([sys.executable,HERE/script,'--output',folder],out/f'{name}.log')
        if not (folder/'verification.json').exists():run([sys.executable,HERE/verifier,'--run',folder],out/f'{name}-verification.log')
    publish('research: verify realistic-delivery timing heartbeat and worker stall recovery')
    kit=out/'LANS_Interface_Python310_Kit';models=ROOT/'docs/research/reviewer-aligned-v3/portable-actor'
    if not kit.exists():run([sys.executable,HERE/'export_full_laptop.py','--profile','fresh_v4','--actor-dir',models,'--output',kit],out/'kit-export.log')
    manifest=json.loads((kit/'bundle-manifest.json').read_text())
    for n,h in manifest['sha256'].items():assert hashlib.sha256((kit/n).read_bytes()).hexdigest()==h
    smoke=out/'kit-smoke'
    if not (smoke/'summary.json').exists():
        if smoke.exists():raise RuntimeError('Partial kit smoke preserved; inspect before retry')
        run([args.smoke_python,kit/'tools/controller_review/laptop_full_controller.py','--profile','fresh_v4','--models',kit/'actor','--seconds','1','--output',smoke],out/'kit-smoke.log',cwd=kit)
    if not (smoke/'verification.json').exists():run([args.smoke_python,kit/'tools/controller_review/verify_full_laptop.py','--run',smoke,'--models',kit/'actor'],out/'kit-verification.log',cwd=kit)
    publish('tools: verify experimental freshness-interface Python3.10 software-plant kit')
    run([sys.executable,HERE/'finish_interface4.py','--run',out],out/'report-export.log')
    publish('docs: publish deep diagnosis corrections and remaining evidence gaps')
    print((out/'completion-status.json').read_text())


if __name__=='__main__':main()
