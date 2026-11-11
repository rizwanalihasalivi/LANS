"""New prospective comparison for the eight-knot PPO endpoint."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,math,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.controller import Proposal
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v9.learning import setup
from tools.ppo_benefit_v10.core import PARAMS,observation as scalar_observation
from .control import Controller,PlanProposal
from .learning import ROOT,DATA,features
from .probe import teacher,dump
from .train import snapshot

OUT=DATA/'evaluation';SEEDS=(42,43,44);MODES=('lqr','adaptive','teacher','scalar','bc','ppo');MODELS=None


def cases():
    rng=np.random.default_rng(2134113);result=[]
    for scenario in ('following','merge','crossing','curved'):
        for speed in (8.,12.,16.):
            for delay in (0.,.05,.1):
                for mirror in (-1,1):
                    result.append(dict(id=len(result),stage='ppo_sequence_prospective',scenario=scenario,speed=speed,delay=delay,mirror=mirror,
                        stiffness=float(rng.uniform(.75,1.25)),lateral=float(rng.uniform(.15,.45))*mirror,heading=float(rng.uniform(-.02,.02)),
                        phase=float(rng.uniform(10,28)),amplitude=float(rng.uniform(.9,1.3)),npc_x_shift=float(rng.uniform(-5,5)),
                        npc_speed_scale=float(rng.uniform(.75,1.25)),network='nominal',network_seed=int(rng.integers(1_200_000_000,1_900_000_000))))
    return result


def prepare():
    OUT.mkdir(exist_ok=False);policies={}
    for mode in ('scalar','bc','ppo'):
        for seed in SEEDS:
            path=ROOT/f'results/ppo-benefit-v10/policies-anchor/seed-{seed}/policy.zip' if mode=='scalar' else DATA/f'policies/seed-{seed}/{"bc-policy" if mode=="bc" else "policy"}.zip'
            policies[f'{mode}-{seed}']=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
    p=dict(cases=cases(),modes=MODES,seeds=SEEDS,episodes=864,policies=policies,source_hashes=snapshot(OUT),
        bootstrap_seed=2134114,target_increment_percent=10.,no_model_or_case_selection=True)
    dump(OUT/'protocol.json',p);return p


def initialize():
    import torch
    from stable_baselines3 import PPO
    global MODELS
    torch.set_num_threads(1);p=json.loads((OUT/'protocol.json').read_text());MODELS={}
    for key,r in p['policies'].items():
        assert sha(ROOT/r['path'])==r['sha256'];m=PPO.load(ROOT/r['path'],device='cpu')
        assert m.observation_space.shape==((30,) if key.startswith('scalar') else (40,))
        assert m.action_space.shape==((1,) if key.startswith('scalar') else (8,));MODELS[key]=m


def run(case,mode,seed,steps=120):
    cls=Base if mode in ('lqr','adaptive','scalar') else Controller
    internal='lqr' if mode=='lqr' else ('hybrid' if mode=='scalar' else 'deterministic')
    c,clock,ego,npcs,net=setup(case,internal,cls,dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
    rows=[];pending=None;sequence=0;last=np.zeros(8)
    for i in range(steps):
        now=i*.05;clock.now=now;net.emit(now,ego,npcs,c.inbox);accepted=None
        if pending is not None:
            accepted=c.accept(pending,now) if mode=='scalar' else c.accept_plan(pending,now);pending=None
        decision=c.decide(now);query=None;label=None
        if mode not in ('lqr','adaptive'):
            if mode=='scalar':query,valid=scalar_observation(c,now,float(last[0]))
            else:query,valid=features(c,now,last)
            if valid:
                if mode=='teacher':value,_=teacher(c,now);value=np.asarray(value)
                else:value,_=MODELS[f'{mode}-{seed}'].predict(query,deterministic=True)
                value=np.clip(np.asarray(value,float).ravel(),-1,1);sequence+=1
                if mode=='scalar':
                    last=np.r_[value[0],np.zeros(7)];pending=Proposal(sequence,c.inbox.latest['ego'].observed_s,now,float(value[0])*.08,now)
                else:
                    assert value.shape==(8,);last=value;pending=PlanProposal(sequence,c.inbox.latest['ego'].observed_s,now,now,tuple(value))
                label=value.tolist()
        before=ego.copy();previous=c.applied;ego=c.apply(now,ego,case['stiffness']);move_npcs(npcs,.05,c.route,case['scenario'])
        truth=truth_metrics(ego,npcs,c.route,c.cfg)
        rows.append(dict(**decision,**truth,tick=i,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),
            npc_truth={name:z.tolist() for name,z in npcs.items()},applied_steering=c.applied.steering,applied_accel=c.applied.accel,
            steering_rate=(c.applied.steering-previous.steering)/.05,label=label,observation=None if query is None else query.tolist(),accepted=accepted))
        if truth['collision'] or abs(truth['error'])>2.5:break
    n=len(rows);record=dict(case=case,mode=mode,seed=seed,ticks=n,expected_ticks=steps,
        failed=n<steps or any(r['collision'] or r['corridor_exceeded'] for r in rows),collisions=sum(r['collision'] for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(steps-n)*6.25)/steps),
        heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
        rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(ego[0]),
        selected_ticks=sum(r['source'] in ('ppo','ppo_plan') for r in rows))
    return record,rows


def worker(job):
    case,mode,seed=job;record,rows=run(case,mode,seed);path=OUT/f'{case["id"]:03d}-{mode}-{seed}.jsonl'
    assert not path.exists();path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(raw_sha256=sha(path),protocol_sha256=sha(OUT/'protocol.json'));dump(path.with_suffix('.json'),record);return record


def assess(records):
    ids=sorted({r['case']['id'] for r in records});lookup={(r['case']['id'],r['mode'],r['seed']):r for r in records}
    assert len(records)==len(lookup)==12*len(ids)
    metrics={m:{key:float(np.mean([r[key] for r in records if r['mode']==m])) for key in
        ('rmse_m','heading_rms','rate_rms','progress_m')} for m in MODES};comparisons={}
    for mode in MODES:
        if mode=='ppo':continue
        groups={};progress=[]
        for i in ids:
            refs=[lookup[(i,mode,s)] for s in (SEEDS if mode in ('scalar','bc') else [0])];pp=[lookup[(i,'ppo',s)] for s in SEEDS];case=refs[0]['case']
            key=(case['scenario'],case['speed'],case['delay']);groups.setdefault(key,[]).append([np.mean([r['rmse_m'] for r in refs]),np.mean([r['rmse_m'] for r in pp])])
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in refs]) for r in pp)
        pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);avg=pairs.mean(axis=0)
        draw=np.random.default_rng(2134114).integers(len(pairs),size=(5000,len(pairs)));samples=pairs[draw].mean(axis=1)
        comparisons[mode]=dict(gain_percent=float(100*(1-avg[1]/avg[0])),ci95_percent=np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist(),
            heading_ratio=metrics['ppo']['heading_rms']/metrics[mode]['heading_rms'],rate_ratio=metrics['ppo']['rate_rms']/metrics[mode]['rate_rms'],
            minimum_progress_ratio=float(min(progress)),clusters=len(pairs))
    reasons=[];actors={}
    for seed in SEEDS:
        rr=[lookup[(i,'ppo',seed)] for i in ids];base=[lookup[(i,'lqr',0)] for i in ids]
        actors[str(seed)]=dict(mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),failures=sum(r['failed'] for r in rr),
            selected_ticks=sum(r['selected_ticks'] for r in rr),gain_vs_adaptive_percent=float(100*(1-np.mean([r['rmse_m'] for r in rr])/metrics['adaptive']['rmse_m'])))
        if any(r['failed'] for r in rr):reasons.append(f'actor_{seed}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(rr,base)):reasons.append(f'actor_{seed}_progress')
        for name in ('heading_rms','rate_rms'):
            if np.mean([r[name] for r in rr])>1.1*np.mean([r[name] for r in base]):reasons.append(f'actor_{seed}_{name}')
    if comparisons['adaptive']['gain_percent']<10:reasons.append('requested_10_mean_gain')
    for mode in ('adaptive','scalar','bc'):
        if comparisons[mode]['ci95_percent'][0]<=0:reasons.append('confidence_'+mode)
    return dict(metrics=metrics,comparisons=comparisons,actors=actors,requested_10_passed=not reasons,reasons=reasons,
        failures={m:sum(r['failed'] for r in records if r['mode']==m) for m in MODES})


def main():
    p=prepare();records=[];jobs=[(c,m,s) for c in p['cases'] for m in MODES for s in (SEEDS if m in ('scalar','bc','ppo') else [0])]
    assert len(jobs)==864
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            records.append(f.result())
            if len(records)%24==0:print('SEQUENCE EVALUATION',len(records),'/864',flush=True)
    records.sort(key=lambda r:(r['case']['id'],r['mode'],r['seed']));dump(OUT/'summary.json',records)
    dump(OUT/'assessment.json',assess(records));print('ALL 864 NEW OUTCOMES SAVED',flush=True)


if __name__=='__main__':main()
