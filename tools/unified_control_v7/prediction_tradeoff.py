"""Matched-LQR check of the prior prediction ablation's quality trade-off."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_control_v6 import ablation
from tools.unified_control_v6.control import Controller as Legacy

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'results/proposal-completion-v6/ablations'
OUTPUT=ROOT/'results/causal-v7/prediction-diagnosis'


class LQR(Legacy):
    def __init__(self,*args,**kwargs):
        kwargs.update(adaptive=False,mpc=False,mode='lqr',deterministic_grid=())
        super().__init__(*args,**kwargs)


def worker(case):
    key=f'{case["id"]:03d}-lqr';raw=OUTPUT/(key+'.jsonl');meta=OUTPUT/(key+'.json')
    if meta.exists():
        record=json.loads(meta.read_text());assert sha(raw)==record['raw_sha256'];return record
    assert not raw.exists()
    choice=dict(horizon=2.)
    record,rows=ablation.run_episode(case,'without_ppo',None,choice,LQR)
    record['variant']='matched_calibrated_lqr';ablation.audit(record,rows)
    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record['raw_sha256']=sha(raw);meta.write_text(json.dumps(clean(record),indent=2));return record


def main():
    OUTPUT.mkdir(parents=True,exist_ok=False);old=json.loads((SOURCE/'protocol.json').read_text())
    assert old['config']['horizon']==2.
    files=[Path(__file__),ROOT/'tools/unified_control_v6/ablation.py',ROOT/'tools/unified_control_v6/control.py',
        ROOT/'tools/unified_control_v4/control.py',ROOT/'integrations/unified_lans/physics.py']
    protocol=dict(scope='retrospective matched-baseline diagnosis, not a new tuning cohort',cases=old['cases'],
        source_protocol_sha256=sha(SOURCE/'protocol.json'),old_summary_sha256=sha(SOURCE/'summary.json'),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files})
    (OUTPUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        dest=OUTPUT/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    records=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for future in as_completed([pool.submit(worker,c) for c in old['cases']]):records.append(future.result())
    old_records=json.loads((SOURCE/'summary.json').read_text());output=[]
    for profile in ['all','nominal','command_delay','traffic_blackout_brake','ego_blackout']:
        baseline=[r for r in records if profile=='all' or r['case']['profile']==profile]
        for variant in ['full','without_application_prediction']:
            rr=[r for r in old_records if r['variant']==variant and (profile=='all' or r['case']['profile']==profile)]
            heading=float(np.mean([r['heading_rms'] for r in rr])/np.mean([r['heading_rms'] for r in baseline]))
            rate=float(np.mean([r['rate_rms'] for r in rr])/np.mean([r['rate_rms'] for r in baseline]))
            output.append(dict(profile=profile,variant=variant,episodes=len(rr),
                mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),mean_heading_ratio_to_lqr=heading,mean_rate_ratio_to_lqr=rate,
                heading_rate_quality_passed=bool(heading<=1.10+1e-12 and rate<=1.10+1e-12),
                minimum_clearance_m=min(r['min_clearance'] for r in rr)))
    (OUTPUT/'lqr_summary.json').write_text(json.dumps(clean(records),indent=2))
    (OUTPUT/'quality_comparison.json').write_text(json.dumps(output,indent=2))
    print(json.dumps(output,indent=2),flush=True)


if __name__=='__main__':main()
