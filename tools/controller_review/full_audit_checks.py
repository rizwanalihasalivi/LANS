"""Run bounded active-contract suites in isolated processes; no research training."""
import argparse,concurrent.futures,json,os,re,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SUITES=['tests/test_controller_remediation.py','tests/test_aris_remediation.py','tests/test_full_audit_root.py',
'integrations/webots/test_adapter.py','integrations/webots/research/test-research.py','integrations/webots/research/test-native-boundaries.py',
'integrations/webots/research/revision2/test_gate.py','integrations/webots/research/revision3/test_range.py',
'integrations/webots/research/revision4/test_contracts.py','integrations/webots/research/revision4/test_screening.py',
'integrations/webots/research/revision5/test_execution.py','integrations/webots/research/revision5/test_evaluation.py','integrations/webots/research/revision5/test_robust_gate.py',
'integrations/webots/research/revision6/test_training.py','integrations/webots/research/revision6/test_evaluation.py',
'integrations/webots/research/revision7/test_oracle.py','integrations/webots/research/revision7/test_submission.py',
'integrations/webots/research/revision8/test_step2.py','integrations/webots/research/revision9/test_step3.py',
'integrations/webots/research/revision10/test_diagnostic.py','integrations/webots/research/revision11/test_attribution.py']

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/lans-full-audit-mpl',NUMBA_CACHE_DIR='/tmp/lans-full-audit-numba')
 def run(item):
  index,path=item;started=time.time()
  try:
   process=subprocess.Popen([sys.executable,str(ROOT/path),'-v'],cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
   output,_=process.communicate(timeout=180);code=process.returncode
  except subprocess.TimeoutExpired:
   try:os.killpg(process.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   output,_=process.communicate();output+='\nTIMEOUT after180s';code=124
  (a.output/f'{index:02d}.txt').write_text(output)
  result=dict(path=path,exit_code=code,tests=sum(int(n) for n in re.findall(r'Ran (\d+) tests?',output)),wall_s=time.time()-started,log=f'{index:02d}.txt')
  print(path,code,flush=True);return result
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,enumerate(SUITES)))
 result=dict(suites=len(rows),test_count=sum(r['tests'] for r in rows),passed=all(r['exit_code']==0 for r in rows),results=rows)
 (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
