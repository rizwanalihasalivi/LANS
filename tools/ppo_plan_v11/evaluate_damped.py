"""Registered optimizer-correction comparison on the same prospective cohort."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,multiprocessing as mp
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from .learning import ROOT,DATA
from .train import snapshot
from .probe import dump
from . import evaluate as base

OUT=DATA/'damped-evaluation'


def paired(reference,candidate):
    p=json.loads((DATA/'evaluation/protocol.json').read_text());old={(r['case']['id'],r['seed']):r for r in reference if r['mode']=='ppo'}
    new={(r['case']['id'],r['seed']):r for r in candidate};groups={}
    for case in p['cases']:
        i=case['id'];groups.setdefault((case['scenario'],case['speed'],case['delay']),[]).append([
            np.mean([old[(i,s)]['rmse_m'] for s in base.SEEDS]),np.mean([new[(i,s)]['rmse_m'] for s in base.SEEDS])])
    pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);avg=pairs.mean(axis=0)
    draw=np.random.default_rng(2134114).integers(36,size=(5000,36));samples=pairs[draw].mean(axis=1)
    return dict(gain_percent=float(100*(1-avg[1]/avg[0])),ci95_percent=np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist(),clusters=36)


def initialize():
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1);base.MODELS={f'ppo-{seed}':PPO.load(DATA/f'policies-damped/seed-{seed}/policy.zip',device='cpu') for seed in base.SEEDS}


def worker(job):
    case,seed=job;record,rows=base.run(case,'ppo',seed);path=OUT/f'{case["id"]:03d}-ppo-{seed}.jsonl'
    assert not path.exists();path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(raw_sha256=sha(path),protocol_sha256=sha(OUT/'protocol.json'),training_arm='actor_step_damped')
    dump(path.with_suffix('.json'),record);return record


def main():
    OUT.mkdir(exist_ok=False);reference=json.loads((DATA/'evaluation/protocol.json').read_text())
    declaration=json.loads((DATA/'policies-damped/declaration.json').read_text());assert declaration['original_assessment_not_available']
    policies={f'ppo-{seed}':dict(path=str((DATA/f'policies-damped/seed-{seed}/policy.zip').relative_to(ROOT)),
        sha256=sha(DATA/f'policies-damped/seed-{seed}/policy.zip')) for seed in base.SEEDS}
    p=dict(cases=reference['cases'],policies=policies,episodes=216,source_hashes=snapshot(OUT),
        declaration_sha256=sha(DATA/'policies-damped/declaration.json'),reference_summary_sha256=sha(DATA/'evaluation/summary.json'))
    dump(OUT/'protocol.json',p);records=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for f in as_completed([pool.submit(worker,(c,s)) for c in p['cases'] for s in base.SEEDS]):
            records.append(f.result())
            if len(records)%24==0:print('DAMPED EVALUATION',len(records),'/216',flush=True)
    records.sort(key=lambda r:(r['case']['id'],r['seed']));dump(OUT/'summary.json',records)
    original=json.loads((DATA/'evaluation/summary.json').read_text());combined=[r for r in original if r['mode']!='ppo']+records
    result=base.assess(combined);result['comparisons']['original_sequence_ppo']=paired(original,records)
    result['arm']='actor_step_damped';dump(OUT/'assessment.json',result);print('ALL 216 CORRECTED OUTCOMES SAVED',flush=True)


if __name__=='__main__':main()
