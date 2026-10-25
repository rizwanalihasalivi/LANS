"""Reproduce missing fallback eligibility in pre-audit selection; no experiment runs."""
import ast,json,subprocess,sys,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.repo/'integrations/webots/research/revision9'))
import evaluate9
from test_step3 import TransferContracts
old_source=subprocess.check_output(['git','show','048ee96:integrations/webots/research/revision9/evaluate9.py'],cwd=a.repo,text=True)
node=next(x for x in ast.parse(old_source).body if isinstance(x,ast.FunctionDef) and x.name=='select')
space=dict(evaluate9.__dict__);exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen-old-select>','exec'),space)
rows=TransferContracts().selection_rows()
for row in rows:
 if row['method']=='scratch_50000' and row['scenario']=='latency100':row['penalized_rmse']=.01;row['active_fraction']=.2
before=space['select'](rows);after=evaluate9.select(rows)
result={str(seed):{'before_selected_steps':before[f'scratch-{seed}']['steps'],'before_candidate_eligible':before[f'scratch-{seed}']['candidates'][2]['eligible'],'after_selected_steps':after[f'scratch-{seed}']['steps'],'after_rejection_reasons':after[f'scratch-{seed}']['candidates'][2]['reasons']} for seed in evaluate9.P['rl_seeds']}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
