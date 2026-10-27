"""Repository source inventory; static coverage is not a manual line-by-line audit."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
paths=set(subprocess.check_output(['git','ls-files','*.py'],cwd=ROOT,text=True).splitlines())
paths.update(str(f.relative_to(ROOT)) for f in (ROOT/'tools/reviewer_v10').glob('*.py'))
rows=[];errors=[]
for name in sorted(paths):
    f=ROOT/name
    if not f.is_file():continue
    data=f.read_bytes();status='syntax_valid'
    try:ast.parse(data,filename=name)
    except (SyntaxError,UnicodeError) as e:status='syntax_error';errors.append(dict(path=name,error=str(e)))
    rows.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),status=status,scope='historical_snapshot' if name.startswith('docs/') else 'source_inventory'))
critical=['tools/reviewer_campaign/environment.py','tools/reviewer_campaign/supervisor.py','tools/reviewer_v3/aligned.py','tools/reviewer_v4/interface4.py','tools/reviewer_v5/history5.py','tools/reviewer_v6/credit6.py','tools/reviewer_v7/compensation.py','tools/reviewer_v8/recovery8.py','tools/reviewer_v8/expiry_cost8.py','tools/reviewer_v9/env9.py','tools/reviewer_v9/features9.py','tools/reviewer_v9/model9.py','tools/reviewer_v9/train9.py','tools/reviewer_v9/export9.py','tools/reviewer_v9/study9.py','tools/reviewer_v9/runtime9.py','tools/controller_review/realtime_kernels.py','tools/controller_review/run_single_pipeline.py','tools/controller_review/verify_development9.py','tools/controller_review/import_laptop9.py','integrations/webots/research/revision2/plant.py','integrations/webots/research/revision7/kernels.py','integrations/webots/research/revision9/policy9.py','integrations/webots/research/comparison.py','integrations/webots/research/core.py']
a.output.write_text(json.dumps(dict(scope='All tracked Python files plus new audit sources receive inventory/hash/AST checks. Detailed semantic audit covers listed active critical path plus all new v10 modules, with previous root audits referenced; AST success is not proof of algorithm correctness or a claim every historical line was manually reviewed.',files=len(rows),historical_snapshots=sum(r['scope']=='historical_snapshot' for r in rows),syntax_errors=errors,detailed_active_path=critical,inventory=rows),indent=2)+'\n')
print('Inventoried',len(rows),'Python files; syntax errors',len(errors))
