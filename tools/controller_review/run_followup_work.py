"""One-command resume of frozen development, timing, portable kit and report."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--smoke-python',default=sys.executable)
    args=p.parse_args();out=ROOT/'docs/research/reviewer-followup-v2'
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
        NUMBA_CACHE_DIR='/tmp/lans-followup-kit-cache',MPLCONFIGDIR='/tmp/lans-followup-kit-mpl')
    def run(command,log,cwd=ROOT):
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('w') as handle:subprocess.run(list(map(str,command)),cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT,check=True)
    def publish(message):
        if not args.publish:return
        subprocess.run(['git','add','-f',str(out.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
            subprocess.run(['git','commit','-m',message],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin',branch],cwd=ROOT,check=True)
    if not (out/'decision.json').exists():
        run([sys.executable,ROOT/'tools/reviewer_followup/run.py'],out/'resume-development.log')
    if not (out/'actor-verification.json').exists():
        run([sys.executable,HERE/'verify_followup_actors.py','--run',out],out/'actor-verification.log')
    timing=out/'timing'
    if not (timing/'absolute/summary.json').exists():
        if timing.exists():raise RuntimeError('Incomplete timing run preserved: inspect it before choosing a new output; no silent retry')
        run([sys.executable,HERE/'realtime_followup.py','--models',ROOT/'docs/research/reviewer-causal-v1/export','--output',timing],out/'timing.log')
    for profile in ('sleep','absolute'):
        run([sys.executable,HERE/'verify_realtime_optimized.py','--run',timing/profile,
             '--model-root',ROOT/'docs/research/reviewer-causal-v1/export'],out/f'timing-{profile}-verification.log')
    publish('research: verify original-deadline timer comparison and all causal proposals')
    kit=out/'LANS_Full_Controller_Kit'
    if not (kit/'bundle-manifest.json').exists():
        if kit.exists():raise RuntimeError('Incomplete portable kit preserved; inspect before retry')
        run([sys.executable,HERE/'export_full_laptop.py','--output',kit],out/'kit-export.log')
    smoke=out/'kit-smoke'
    if not (smoke/'summary.json').exists():
        if smoke.exists():raise RuntimeError('Incomplete smoke preserved; inspect before retry')
        run([args.smoke_python,kit/'tools/controller_review/laptop_full_controller.py',
             '--models',kit/'actor','--output',smoke,'--seconds','1.5'],out/'kit-smoke.log',cwd=kit)
    run([args.smoke_python,kit/'tools/controller_review/verify_full_laptop.py','--run',smoke,'--models',kit/'actor'],out/'kit-verification.log',cwd=kit)
    publish('tools: verify portable full-controller Python3.10 laptop SIL kit')
    run([sys.executable,HERE/'write_followup_report.py','--run',out],out/'report-export.log')
    publish('docs: publish verified follow-up results reports and remaining evidence gaps')
    print((out/'completion-status.json').read_text())
    print('Hardware/actual laptop and vehicle execution require external measurements. Reserved confirmation stays gated.')


if __name__=='__main__':main()
