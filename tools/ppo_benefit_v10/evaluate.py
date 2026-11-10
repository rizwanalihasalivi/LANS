"""Frozen prospective whole-run PPO attribution, including BC-only controls."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,math,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.controller import Proposal
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_control_v9.learning import setup
from tools.unified_control_v8.control import Controller
from .core import ROOT,DATA,PARAMS,observation,teacher,dump

OUT=DATA/'evaluation';SEEDS=(42,43,44);MODELS=None
MODES=('lqr','adaptive','teacher','old','bc','ppo')


def cases():
    rng=np.random.default_rng(991123);result=[]
    for scenario in ['following','merge','crossing','curved']:
        for speed in [8.,12.,16.]:
            for delay in [0.,.05,.1]:
                for mirror in [-1,1]:
                    result.append(dict(id=len(result),stage='ppo_benefit_prospective',scenario=scenario,
                        speed=speed,delay=delay,mirror=mirror,stiffness=float(rng.uniform(.75,1.25)),
                        lateral=float(rng.uniform(.15,.45))*mirror,heading=float(rng.uniform(-.02,.02)),
                        phase=float(rng.uniform(10.,28.)),amplitude=float(rng.uniform(.9,1.3)),
                        npc_x_shift=float(rng.uniform(-5,5)),npc_speed_scale=float(rng.uniform(.75,1.25)),
                        network='nominal',network_seed=int(rng.integers(1_100_000_000,1_900_000_000))))
    return result


def prepare():
    OUT.mkdir(parents=True,exist_ok=False)
    from .verify import check_sources
    teacher_protocol=check_sources(DATA/'teacher')
    # Keep the original collection snapshot and pin the repaired training driver
    # separately; its unrelated initialization/logger fixes do not alter labels.
    hashes={name:sha(ROOT/name) for name in teacher_protocol['source_hashes']}
    hashes[str(Path(__file__).relative_to(ROOT))]=sha(Path(__file__))
    policies={}
    for mode in ('old','bc','ppo'):
        for seed in SEEDS:
            path=ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip' if mode=='old' else DATA/f'policies/seed-{seed}/{"bc-policy" if mode=="bc" else "policy"}.zip'
            policies[f'{mode}-{seed}']=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
    protocol=dict(cases=cases(),modes=MODES,seeds=SEEDS,total_episodes=864,source_hashes=hashes,policies=policies,
        teacher_protocol_sha256=sha(DATA/'teacher/protocol.json'),
        scoring='Original full-six-second RMSE; early stop only collision or absolute error >2.5; corridor >1.75 disqualifies.',
        final_once=True,model_selection=False)
    dump(OUT/'protocol.json',protocol)
    for name,digest in hashes.items():
        assert sha(ROOT/name)==digest,('Frozen source changed',name)
        dest=OUT/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return protocol


def initialize():
    import torch
    from stable_baselines3 import PPO
    global MODELS
    torch.set_num_threads(1);p=json.loads((OUT/'protocol.json').read_text());MODELS={}
    for key,record in p['policies'].items():
        path=ROOT/record['path'];assert sha(path)==record['sha256'];MODELS[key]=PPO.load(path,device='cpu')


def run(case,mode,seed,steps=120):
    pipe,clock,ego,npcs,net=setup(case,'lqr' if mode=='lqr' else ('deterministic' if mode=='adaptive' else 'hybrid'),
        Controller,dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
    rows=[];pending=None;sequence=0;last_action=0.
    for tick in range(steps):
        now=tick*.05;clock.now=now;net.emit(now,ego,npcs,pipe.inbox);accepted=None
        if pending is not None:
            accepted=pipe.accept(pending,now);pending=None
        decision=pipe.decide(now);obs,valid=observation(pipe,now,last_action);query=None;teacher_info=None
        if mode not in ('lqr','adaptive') and valid:
            if mode=='teacher':action,teacher_info=teacher(pipe,now)
            else:
                model=MODELS[f'{mode}-{seed}'];query=obs[:17] if mode=='old' else obs
                value,_=model.predict(query,deterministic=True);action=float(np.asarray(value).ravel()[0])
            last_action=float(np.clip(action,-1,1));sequence+=1
            pending=Proposal(sequence,pipe.inbox.latest['ego'].observed_s,now,last_action*.08,now)
        before=ego.copy();previous=pipe.applied;ego=pipe.apply(now,ego,case['stiffness'])
        move_npcs(npcs,.05,pipe.route,case['scenario']);truth=truth_metrics(ego,npcs,pipe.route,pipe.cfg)
        rows.append(dict(tick=tick,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),
            npc_truth={k:v.tolist() for k,v in npcs.items()},**truth,**decision,
            observation_after_issue=obs.tolist(),submitted_action=last_action if pending is not None else None,
            teacher_info=teacher_info,accepted_before_decision=accepted,applied_steering=pipe.applied.steering,
            applied_accel=pipe.applied.accel,steering_rate=(pipe.applied.steering-previous.steering)/.05))
        if truth['collision'] or abs(truth['error'])>2.5:break
    result=dict(case=case,mode=mode,seed=seed,ticks=len(rows),expected_ticks=steps,
        failed=len(rows)<steps or any(r['collision'] or r['corridor_exceeded'] for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(steps-len(rows))*6.25)/steps),
        heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),
        rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])),progress_m=float(ego[0]),
        collisions=sum(r['collision'] for r in rows),ppo_ticks=sum(r['source']=='ppo' for r in rows),
        ppo_evaluated=sum('ppo' in r['eligible'] for r in rows))
    return result,rows


def worker(job):
    case,mode,seed=job;path=OUT/f'{case["id"]:03d}-{mode}-{seed}.jsonl'
    assert not path.exists(),('Preserve existing outcome',path)
    record,rows=run(case,mode,seed)
    path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(raw_sha256=sha(path),protocol_sha256=sha(OUT/'protocol.json'));dump(path.with_suffix('.json'),record)
    return record


def assess(records):
    ids=sorted({r['case']['id'] for r in records});lookup={(r['case']['id'],r['mode'],r['seed']):r for r in records}
    assert len(lookup)==len(records)==len(ids)*12
    metrics={mode:{key:float(np.mean([r[key] for r in records if r['mode']==mode])) for key in
        ('rmse_m','heading_rms','rate_rms','progress_m')} for mode in MODES}
    comparisons={}
    for mode in MODES:
        if mode=='ppo':continue
        clusters={};progress=[]
        for i in ids:
            refs=[lookup[(i,mode,s)] for s in (SEEDS if mode in ('old','bc') else [0])]
            pp=[lookup[(i,'ppo',s)] for s in SEEDS];case=refs[0]['case'];key=(case['scenario'],case['speed'],case['delay'])
            clusters.setdefault(key,[]).append([np.mean([r['rmse_m'] for r in refs]),np.mean([r['rmse_m'] for r in pp])])
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in refs]) for r in pp)
        pairs=np.array([np.mean(v,axis=0) for v in clusters.values()]);mean=pairs.mean(axis=0)
        indices=np.random.default_rng(991124).integers(len(pairs),size=(5000,len(pairs)));boot=pairs[indices].mean(axis=1)
        comparisons[mode]=dict(gain_percent=float(100*(1-mean[1]/mean[0])),
            ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist(),clusters=len(pairs),
            heading_ratio=metrics['ppo']['heading_rms']/metrics[mode]['heading_rms'],
            rate_ratio=metrics['ppo']['rate_rms']/metrics[mode]['rate_rms'],minimum_progress_ratio=float(min(progress)))
    reasons=[];actors={}
    for seed in SEEDS:
        pp=[lookup[(i,'ppo',seed)] for i in ids];base=[lookup[(i,'lqr',0)] for i in ids]
        actors[str(seed)]=dict(ppo_ticks=sum(r['ppo_ticks'] for r in pp),failures=sum(r['failed'] for r in pp),
            mean_rmse_m=float(np.mean([r['rmse_m'] for r in pp])),
            gain_vs_adaptive_percent=float(100*(1-np.mean([r['rmse_m'] for r in pp])/metrics['adaptive']['rmse_m'])),
            gain_vs_old_same_seed_percent=float(100*(1-np.mean([r['rmse_m'] for r in pp])/np.mean([lookup[(i,'old',seed)]['rmse_m'] for i in ids]))),
            gain_vs_bc_same_seed_percent=float(100*(1-np.mean([r['rmse_m'] for r in pp])/np.mean([lookup[(i,'bc',seed)]['rmse_m'] for i in ids]))),
            minimum_lqr_progress_ratio=min(r['progress_m']/b['progress_m'] for r,b in zip(pp,base)))
        if any(r['failed'] for r in pp):reasons.append(f'actor_{seed}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(pp,base)):reasons.append(f'actor_{seed}_progress')
        for key in ('heading_rms','rate_rms'):
            if np.mean([r[key] for r in pp])>1.1*np.mean([r[key] for r in base]):reasons.append(f'actor_{seed}_{key}')
    for ref in ('adaptive','old'):
        if comparisons[ref]['ci95_percent'][0]<=0:reasons.append('confidence_'+ref)
    return dict(metrics=metrics,comparisons=comparisons,actors=actors,primary_success=not reasons,reasons=reasons,
        ppo_finetuning_positive=comparisons['bc']['ci95_percent'][0]>0,
        descriptive_old_gain_vs_adaptive_percent=100*(1-metrics['old']['rmse_m']/metrics['adaptive']['rmse_m']),
        descriptive_bc_gain_vs_adaptive_percent=100*(1-metrics['bc']['rmse_m']/metrics['adaptive']['rmse_m']),
        requested_30=not reasons and all(r['gain_percent']>=30 for r in comparisons.values()),
        failures={m:sum(r['failed'] for r in records if r['mode']==m) for m in MODES},
        selection={m:sum(r['ppo_ticks'] for r in records if r['mode']==m) for m in MODES})


def main():
    protocol=prepare();jobs=[(case,mode,seed) for case in protocol['cases'] for mode in MODES for seed in
        (SEEDS if mode in ('old','bc','ppo') else [0])];assert len(jobs)==864
    result=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            result.append(f.result())
            if len(result)%24==0:print('ATTRIBUTION',len(result),'/864',flush=True)
    result.sort(key=lambda r:(r['case']['id'],r['mode'],r['seed']));dump(OUT/'summary.json',result)
    dump(OUT/'assessment.json',assess(result));print('ALL FIXED OUTCOMES SAVED',flush=True)


if __name__=='__main__':main()
