"""One resumable command; scientific failures remain failures, not silent retries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--laptop-results',type=Path);p.add_argument('--publish',action='store_true');a=p.parse_args();out=ROOT/'docs/research/reviewer-pipeline-v9';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/tmp/lans-v9-numba',MPLCONFIGDIR='/tmp/lans-v9-mpl')
    status={};path=out/'pipeline-status.json'
    def save():path.write_text(json.dumps(dict(stages=status,all_requirements_passed=all(v['state']=='passed' for v in status.values()),scope='Software research pipeline. Hardware/primary-source access and empirical superiority cannot be manufactured.'),indent=2)+'\n')
    def stage(name,cmd,complete=None):
        print(name,flush=True)
        try:
            if complete is None or not complete.exists():
                with (out/(name+'.log')).open('w') as f:subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
            status[name]=dict(state='passed',meaning='Implementation/execution/replay completed; empirical criteria evaluated separately');save();return True
        except Exception as e:
            status[name]=dict(state='execution_error',error=str(e),log=name+'.log');save();return False
    py=sys.executable;helper=ROOT/'tools/controller_review'
    if not stage('prior_evidence',[py,helper/'verify_cache8.py','--run',ROOT/'docs/research/reviewer-recovery-v8']):return 1
    if not stage('matched_development',[py,ROOT/'tools/reviewer_v9/run9.py']):return 1
    decision=json.loads((out/'decision.json').read_text());selected=decision['selected'];status['scientific_selection']=dict(state='passed' if selected else 'failed_requirement',selected=selected,screens=decision['screens']);save()
    if not stage('timing',[py,helper/'timing9.py','--run',out],out/'timing/summary.json'):return 1
    if not stage('timing_replay',[py,helper/'verify_timing9.py','--run',out]):return 1
    timing=json.loads((out/'timing/summary.json').read_text())['profiles']['on'];status['strict_original_10ms']=dict(state='passed' if timing['observed_timing_pass'] else 'failed_requirement',**timing,hard_realtime_guarantee=False);save()
    if not stage('portable_kit',[py,helper/'export_pipeline_kit9.py','--run',out],out/'LANS_Causal_Python310_Kit.zip'):return 1
    kit=out/'LANS_Causal_Python310_Kit';clean=Path('/workspace/lans-target-kit-venv/bin/python')
    if not clean.exists():
        status['packaging_smoke']=dict(state='blocked',reason='Clean minimal Python3.10 interpreter unavailable; do not substitute full Torch environment');save();return 1
    if not stage('packaging_smoke',[clean,kit/'tools/controller_review/laptop_campaign9.py','--models',kit/'actor','--profile','history_comp','--budget-guard','--seconds','.5','--output',out/'kit-smoke'],out/'kit-smoke/summary.json'):return 1
    if a.laptop_results:
        if not stage('target_import',[py,helper/'import_laptop9.py','--run',out,'--results',a.laptop_results],out/'target-laptop/import-verification.json'):return 1
        target=json.loads((out/'target-laptop/import-verification.json').read_text());status['actual_laptop']=dict(state='passed' if target['observed_strict_timing_pass'] else 'failed_requirement',**target)
    else:status['actual_laptop']=dict(state='awaiting_external_run',instruction='Run the new Python3.10 kit on the actual Windows/macOS laptop; submit Results.zip. Cloud smoke is not target evidence.')
    allowed=selected is not None and timing['observed_timing_pass']
    status['reserved_unseen']=dict(state='ready_for_prespecified_confirmation' if allowed else 'blocked',reason='Requires scientific selection and corresponding-model original-deadline timing pass. Never open reserved data to tune a failed candidate.')
    status['native_webots']=dict(state='needs_corresponding_controller_integration' if allowed else 'blocked',reason='Old student/native adapter cannot stand in for this new ABI/controller. No current-model native confirmation claimed.')
    status['robust_vehicle_baseline']=dict(state='needs_research',reason='Existing scalar robust filter is verified, but a matched vehicle reproduction needs a justified disturbance set, terminal safe set/backup and primary algorithm details.')
    status['primary_references']=dict(state='awaiting_primary_source_verification',verified_primary_versions=5,structurally_audited=32,reason='Structural checks and five uploaded papers do not verify the remaining primary sources or establish novelty.')
    status['physical_validation']=dict(state='not_performed',reason='No physical sensor, communication or actuator access; real-vehicle-readiness claims excluded.')
    status['submission']=dict(state='draft_only',reason='Unresolved evidence gates remain. Report the observed outcomes, not assumed superiority or hard real-time guarantees.');save()
    if not stage('evidence_seal',[py,helper/'seal_pipeline9.py','--run',out,'--seal']):return 1
    if not stage('evidence_report',[py,helper/'finish_pipeline9.py','--run',out]):return 1
    if a.publish:
        files=[str(f.relative_to(ROOT)) for f in out.rglob('*') if f.is_file() and '__pycache__' not in f.parts and not any(part.startswith('.venv') for part in f.parts) and f.suffix not in ('.pyc','.nbc','.nbi')]
        subprocess.run(['git','add','-f','--',*files],cwd=ROOT,check=True)
        subprocess.run(['git','add','--','tools/controller_review','tools/reviewer_v9','README.md'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','--quiet','-m','Publish finite matched causal-state pipeline raw replay timing and explicit remaining gates'],cwd=ROOT,check=True)
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin','reports/opening-report-2026-10-26'],cwd=ROOT,check=True)
        local=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','ls-remote','--heads','origin','reports/opening-report-2026-10-26'],cwd=ROOT,text=True).split()[0];assert local==remote
    print(json.dumps(json.loads(path.read_text()),indent=2));return 0 if all(v['state']=='passed' for v in status.values()) else 2

if __name__=='__main__':sys.exit(main())
