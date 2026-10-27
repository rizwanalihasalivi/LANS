"""Resume fixed v5 evidence and package diagnostics without promoting failed arms."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--kit-python',default='/tmp/lans-interface-kit-venv/bin/python');a=p.parse_args()
    out=ROOT/'docs/research/reviewer-history-v5'
    def run(*cmd):subprocess.run([str(x) for x in cmd],cwd=ROOT,check=True)
    if not (out/'decision.json').exists():run(sys.executable,ROOT/'tools/reviewer_v5/run5.py')
    decision=json.loads((out/'decision.json').read_text());arm=decision['selected'] or 'nohistory'
    actor=out/'portable-actor'
    if not actor.exists():run(sys.executable,ROOT/'tools/controller_review/export_history5.py','--run',out,'--arm',arm,'--output',actor)
    manifest=json.loads((actor/'manifest.json').read_text())
    assert all(x['arm']==arm for x in manifest['model_provenance'].values())
    (out/'package-provenance.json').write_text(json.dumps(dict(arm=arm,selected=decision['selected'],diagnostic_only=decision['selected'] is None,profile=manifest['profile'],model_provenance=manifest['model_provenance']),indent=2)+'\n')
    kit=out/'LANS_History_Python310_Kit'
    if not kit.exists():run(sys.executable,ROOT/'tools/controller_review/export_full_laptop.py','--profile','fresh_history','--actor-dir',actor,'--output',kit)
    smoke=out/'kit-smoke'
    if not (smoke/'summary.json').exists():
        assert not smoke.exists(),'Partial evidence exists: inspect rather than overwrite'
        run(a.kit_python,kit/'tools/controller_review/laptop_full_controller.py','--models',kit/'actor','--profile','fresh_history','--seconds','3','--output',smoke)
    run(a.kit_python,kit/'tools/controller_review/verify_full_laptop.py','--run',smoke,'--models',kit/'actor')
    run(sys.executable,ROOT/'tools/controller_review/verify_history_worker_policy.py','--run',out)
    run(sys.executable,ROOT/'tools/controller_review/finish_history5.py','--run',out)
    if a.publish:
        run('git','add','-f','--',out.relative_to(ROOT),':(exclude)**/__pycache__/**',':(exclude)**/*.pyc')
        changed=subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode
        if changed:run('git','commit','-m','Record verified history ablation and diagnostic Python 3.10 kit')
        run('git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26')

if __name__=='__main__':main()
