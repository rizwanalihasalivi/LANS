"""All fixed endpoints on a new, unopened factorial cohort."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,multiprocessing as mp
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.ppo_plan_v11 import evaluate as frozen
from tools.ppo_plan_v11.learning import DATA as V11
from tools.ppo_plan_v11.probe import dump
from .train import ROOT,DATA,SEEDS,snapshot

OUT=DATA/'evaluation';MODES=('lqr','adaptive','scalar','bc','v11','ppo');MODELS={}


def cases():
    rng=np.random.default_rng(2134123);result=[]
    for scenario in ('following','merge','crossing','curved'):
        for speed in (8.,12.,16.):
            for delay in (0.,.05,.1):
                for mirror in (-1,1):
                    result.append(dict(id=len(result),stage='ppo_exploration_prospective',scenario=scenario,speed=speed,delay=delay,mirror=mirror,
                        stiffness=float(rng.uniform(.75,1.25)),lateral=float(rng.uniform(.15,.45))*mirror,heading=float(rng.uniform(-.02,.02)),
                        phase=float(rng.uniform(10,28)),amplitude=float(rng.uniform(.9,1.3)),npc_x_shift=float(rng.uniform(-5,5)),
                        npc_speed_scale=float(rng.uniform(.75,1.25)),network='nominal',network_seed=int(rng.integers(1_200_000_000,1_900_000_000))))
    return result


def prepare():
    assert len(json.loads((DATA/'policies/summary.json').read_text()))==3
    OUT.mkdir(exist_ok=False);policies={}
    for mode in ('scalar','bc','v11','ppo'):
        for seed in SEEDS:
            path={'scalar':ROOT/f'results/ppo-benefit-v10/policies-anchor/seed-{seed}/policy.zip',
                'bc':V11/f'policies/seed-{seed}/bc-policy.zip','v11':V11/f'policies-damped/seed-{seed}/policy.zip',
                'ppo':DATA/f'policies/seed-{seed}/policy.zip'}[mode]
            policies[f'{mode}-{seed}']=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
    p=dict(cases=cases(),modes=MODES,seeds=SEEDS,episodes=1008,policies=policies,source_hashes=snapshot(OUT),
        bootstrap_seed=2134124,target_increment_percent=10.,no_model_or_case_selection=True)
    dump(OUT/'protocol.json',p);return p


def initialize():
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1);p=json.loads((OUT/'protocol.json').read_text());MODELS.clear()
    for key,record in p['policies'].items():
        assert sha(ROOT/record['path'])==record['sha256'];model=PPO.load(ROOT/record['path'],device='cpu')
        assert model.observation_space.shape==((30,) if key.startswith('scalar-') else (40,))
        assert model.action_space.shape==((1,) if key.startswith('scalar-') else (8,));MODELS[key]=model


def worker(job):
    case,mode,seed=job;internal='ppo' if mode=='v11' else mode
    frozen.MODELS={} if mode in ('lqr','adaptive') else {f'{internal}-{seed}':MODELS[f'{mode}-{seed}']}
    record,rows=frozen.run(case,internal,seed);record['mode']=mode
    path=OUT/f'{case["id"]:03d}-{mode}-{seed}.jsonl';assert not path.exists()
    path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(raw_sha256=sha(path),protocol_sha256=sha(OUT/'protocol.json'))
    dump(path.with_suffix('.json'),record);return record


def assess(records):
    lookup={(r['case']['id'],r['mode'],r['seed']):r for r in records};ids=sorted({r['case']['id'] for r in records})
    assert len(records)==len(lookup)==14*len(ids)
    metrics={m:{key:float(np.mean([r[key] for r in records if r['mode']==m])) for key in
        ('rmse_m','heading_rms','rate_rms','progress_m')} for m in MODES};comparisons={}
    for mode in MODES:
        if mode=='ppo':continue
        groups={};progress=[]
        for i in ids:
            refs=[lookup[(i,mode,s)] for s in ((0,) if mode in ('lqr','adaptive') else SEEDS)]
            pp=[lookup[(i,'ppo',s)] for s in SEEDS];c=refs[0]['case']
            groups.setdefault((c['scenario'],c['speed'],c['delay']),[]).append([np.mean([r['rmse_m'] for r in refs]),np.mean([r['rmse_m'] for r in pp])])
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in refs]) for r in pp)
        pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);mean=pairs.mean(axis=0)
        draw=np.random.default_rng(2134124).integers(len(pairs),size=(5000,len(pairs)));sample=pairs[draw].mean(axis=1)
        comparisons[mode]=dict(gain_percent=float(100*(1-mean[1]/mean[0])),ci95_percent=np.quantile(100*(1-sample[:,1]/sample[:,0]),[.025,.975]).tolist(),
            heading_ratio=metrics['ppo']['heading_rms']/metrics[mode]['heading_rms'],rate_ratio=metrics['ppo']['rate_rms']/metrics[mode]['rate_rms'],
            minimum_progress_ratio=float(min(progress)),clusters=len(pairs))
    reasons=[];actors={}
    for seed in SEEDS:
        rr=[lookup[(i,'ppo',seed)] for i in ids];base=[lookup[(i,'lqr',0)] for i in ids]
        actors[str(seed)]=dict(mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),failures=sum(r['failed'] for r in rr),
            selected_ticks=sum(r['selected_ticks'] for r in rr),gain_vs_adaptive_percent=float(100*(1-np.mean([r['rmse_m'] for r in rr])/metrics['adaptive']['rmse_m'])))
        if any(r['failed'] for r in rr):reasons.append(f'actor_{seed}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(rr,base)):reasons.append(f'actor_{seed}_progress')
        for metric in ('heading_rms','rate_rms'):
            if np.mean([r[metric] for r in rr])>1.1*np.mean([r[metric] for r in base]):reasons.append(f'actor_{seed}_{metric}')
    if comparisons['adaptive']['gain_percent']<10:reasons.append('requested_10_mean_gain')
    for mode in ('adaptive','bc','scalar','v11'):
        if comparisons[mode]['ci95_percent'][0]<=0:reasons.append('confidence_'+mode)
    return dict(metrics=metrics,comparisons=comparisons,actors=actors,reasons=reasons,requested_10_passed=not reasons,
        adaptive_ci_lower_at_least_10=comparisons['adaptive']['ci95_percent'][0]>=10,
        failures={m:sum(r['failed'] for r in records if r['mode']==m) for m in MODES})


def main():
    p=prepare();records=[];jobs=[(c,m,s) for c in p['cases'] for m in MODES for s in ((0,) if m in ('lqr','adaptive') else SEEDS)]
    assert len(jobs)==1008
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            records.append(f.result())
            if len(records)%24==0:print('EXPLORATION EVALUATION',len(records),'/1008',flush=True)
    records.sort(key=lambda r:(r['case']['id'],r['mode'],r['seed']));dump(OUT/'summary.json',records)
    dump(OUT/'assessment.json',assess(records));print('ALL 1008 NEW EXPLORATION COMPARISONS SAVED',flush=True)


if __name__=='__main__':main()
