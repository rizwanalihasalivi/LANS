"""Recheck the observed false-braking case after the shared occupancy fix."""
from pathlib import Path
import json,shutil
import numpy as np
from integrations.unified_lans.inference import sha,load_policy
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v7.campaign import make_controller
from tools.unified_control_v6.verify import check_record

ROOT=Path(__file__).resolve().parents[2]


def main():
    import torch
    torch.set_num_threads(1)
    root=ROOT/'results/causal-v8/conflict-regression';root.mkdir(parents=True,exist_ok=False)
    prior=ROOT/'results/causal-v7/engineering/development/004-hybrid-42.json'
    case=json.loads(prior.read_text())['case']
    selections={r:json.loads((ROOT/f'results/causal-v7/{r}/protocol.json').read_text())['selected'] for r in ['confirmation','engineering']}
    files=[Path(__file__),*(ROOT/'integrations/unified_lans').glob('*.py'),
        *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
        *(ROOT/'tools/unified_control_v6').glob('*.py'),*(ROOT/'tools/unified_control_v7').glob('*.py'),
        ROOT/'tools/unified_campaign/study.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    protocol=dict(case=case,selections=selections,prior_case_sha256=sha(prior),
        role='KNOWN_FAILURE_REGRESSION_NOT_FRESH_EVIDENCE',sources={str(p.relative_to(ROOT)):sha(p) for p in files},
        model_hashes={s:sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip') for s in [42,43,44]})
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        target=root/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    models={s:load_policy(ROOT/f'results/python-campaign-v2/policies/seed-{s}') for s in [42,43,44]};records=[]
    for role,actor in [('lqr',0)]+[(r,s) for r in selections for s in [42,43,44]]:
        selection=selections['confirmation' if role=='lqr' else role]
        def factory(*args,**kwargs):return make_controller(*args,selection=selection,adaptive=role!='lqr',mpc=role!='lqr',**kwargs)
        study.Pipeline=factory
        record,rows=study.run_episode(case,'lqr' if role=='lqr' else 'hybrid',models.get(actor),grid=role!='lqr')
        raw=root/f'{role}-{actor}.jsonl';raw.write_text(''.join(json.dumps(clean(row),allow_nan=False)+'\n' for row in rows))
        record.update(controller_role=role,actor=actor,raw_sha256=sha(raw),protocol_sha256=sha(root/'protocol.json'))
        check_record(record,raw);records.append(record)
        print(role,actor,'progress',record['progress_m'],'failure',record['failed'],flush=True)
    base=records[0]
    output=dict(records=records,all_physical_replays_passed=True,
        results=[dict(role=r['controller_role'],actor=r['actor'],progress_ratio=r['progress_m']/base['progress_m'],
                      failed=r['failed'],rmse_m=r['rmse_m']) for r in records],
        source='Observed v7 case; no independent performance or timing claim')
    (root/'summary.json').write_text(json.dumps(output,indent=2))


if __name__=='__main__':main()
