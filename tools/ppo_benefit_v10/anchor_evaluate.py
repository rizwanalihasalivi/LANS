"""Prospective extension registered before reading original performance outcomes."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import argparse,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from .core import ROOT,DATA,dump
from . import evaluate as base

OUT=DATA/'anchor-evaluation'


def paired(records,new_records):
    lookup={(r['case']['id'],r['seed']):r for r in records if r['mode']=='ppo'}
    other={(r['case']['id'],r['seed']):r for r in new_records};groups={}
    for case in json.loads((DATA/'evaluation/protocol.json').read_text())['cases']:
        i=case['id'];key=(case['scenario'],case['speed'],case['delay'])
        groups.setdefault(key,[]).append([np.mean([lookup[(i,s)]['rmse_m'] for s in base.SEEDS]),np.mean([other[(i,s)]['rmse_m'] for s in base.SEEDS])])
    pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);avg=pairs.mean(axis=0)
    draws=np.random.default_rng(991124).integers(len(pairs),size=(5000,len(pairs)));samples=pairs[draws].mean(axis=1)
    return dict(gain_percent=float(100*(1-avg[1]/avg[0])),ci95_percent=np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist(),clusters=len(pairs))


def prepare(directory,policy_directory):
    out=DATA/directory;out.mkdir(exist_ok=False)
    reference=json.loads((DATA/'evaluation/protocol.json').read_text());declaration=json.loads((DATA/'policies-anchor/declaration.json').read_text())
    assert declaration['original_assessment_not_available'] and declaration['protocol_sha256']==sha(Path(__file__).parent/'ANCHOR_PROTOCOL.md')
    hashes={name:sha(ROOT/name) for name in reference['source_hashes']}
    for path in Path(__file__).parent.glob('*.py'):hashes[str(path.relative_to(ROOT))]=sha(path)
    hashes[str((Path(__file__).parent/'ANCHOR_PROTOCOL.md').relative_to(ROOT))]=sha(Path(__file__).parent/'ANCHOR_PROTOCOL.md')
    policies={str(s):sha(DATA/f'{policy_directory}/seed-{s}/policy.zip') for s in base.SEEDS}
    p=dict(cases=reference['cases'],source_hashes=hashes,policies=policies,episodes=216,
        reference_protocol_sha256=sha(DATA/'evaluation/protocol.json'),reference_summary_sha256=sha(DATA/'evaluation/summary.json'),
        declaration_sha256=sha(DATA/'policies-anchor/declaration.json'),no_checkpoint_selection=True,policy_directory=policy_directory)
    dump(out/'protocol.json',p)
    for name in hashes:
        dest=out/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return p


def initialize(policy_directory):
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1);base.MODELS={f'ppo-{s}':PPO.load(DATA/f'{policy_directory}/seed-{s}/policy.zip',device='cpu') for s in base.SEEDS}


def worker(job):
    case,seed,directory,arm=job;out=DATA/directory
    record,rows=base.run(case,'ppo',seed);path=out/f'{case["id"]:03d}-ppo-{seed}.jsonl'
    assert not path.exists();path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(raw_sha256=sha(path),protocol_sha256=sha(out/'protocol.json'),arm=arm)
    dump(path.with_suffix('.json'),record);return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--continued-bc',action='store_true');args=parser.parse_args()
    directory='continued-bc-evaluation' if args.continued_bc else 'anchor-evaluation'
    policy_directory='policies-continued-bc' if args.continued_bc else 'policies-anchor'
    arm='continued_bc' if args.continued_bc else 'teacher_anchored_ppo';out=DATA/directory
    p=prepare(directory,policy_directory);result=[];jobs=[(c,s,directory,arm) for c in p['cases'] for s in base.SEEDS]
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(policy_directory,)) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            result.append(f.result())
            if len(result)%24==0:print('ANCHOR ATTRIBUTION',len(result),'/216',flush=True)
    result.sort(key=lambda r:(r['case']['id'],r['seed']));dump(out/'summary.json',result)
    reference=json.loads((DATA/'evaluation/summary.json').read_text());merged=[r for r in reference if r['mode']!='ppo']+result
    assessment=base.assess(merged);assessment['comparisons']['unregularized_ppo']=paired(reference,result)
    assessment['anchor_vs_unregularized_positive']=assessment['comparisons']['unregularized_ppo']['ci95_percent'][0]>0
    assessment['requested_30']=assessment['requested_30'] and assessment['comparisons']['unregularized_ppo']['gain_percent']>=30
    assessment['arm']=arm;dump(out/'assessment.json',assessment)
    print('ALL 216 ANCHORED OUTCOMES SAVED',flush=True)


if __name__=='__main__':main()
