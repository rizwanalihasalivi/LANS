"""Raw replay of wider-exploration PPO; source-pinned resumable seed audits."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,multiprocessing as mp
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,advance
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v9.learning import setup
from tools.ppo_benefit_v10.core import PARAMS
from tools.ppo_plan_v11.control import Controller,PlanProposal
from tools.ppo_plan_v11.learning import features,shaping,CONTRACT
from tools.ppo_plan_v11.verify_learning import ingest,admitted,equal
from tools.ppo_plan_v11 import verify_learning as frozen_audit
from tools.ppo_plan_v11.probe import dump
from .train import ROOT,DATA,V11,SEEDS,curriculum,optimizer_steps


def sources(folder):
    p=json.loads((folder/'protocol.json').read_text())
    for name,digest in p['source_hashes'].items():
        assert sha(folder/'source'/name)==digest,('Snapshot',name)
        if name.startswith('tools/ppo_explore_v12/') and Path(name).name not in ('train.py','PROTOCOL.md'):continue
        if name.startswith('tools/ppo_plan_v11/') and Path(name).name not in (
            'control.py','learning.py','verify.py','verify_learning.py','evaluate.py','damped.py'):continue
        assert sha(ROOT/name)==digest,('Frozen replay dependency',name)
    return p


def training_worker(seed,limit=None):
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1);folder=DATA/f'policies/seed-{seed}';p=sources(folder)
    m=json.loads((folder/'manifest.json').read_text());assert m['steps']==65536 and sha(folder/'policy.zip')==m['policy_sha256']
    assert sha(V11/f'policies/seed-{seed}/bc-policy.zip')==m['source_bc_sha256']==p['source_bc_sha256']
    assert p['seed']==m['seed']==seed and p['contract']==m['contract']==CONTRACT
    assert p['new_steps']==65536 and p['initial_log_std']==-2.5 and p['actor_step_factor']==.1
    assert p['declaration_sha256']==sha(Path(__file__).parent/'PROTOCOL.md')
    initial_path=folder/'initial-exploration-policy.zip';assert sha(initial_path)==m['initial_policy_sha256']
    initial=PPO.load(initial_path,device='cpu');bc=PPO.load(V11/f'policies/seed-{seed}/bc-policy.zip',device='cpu')
    assert initial.num_timesteps==bc.num_timesteps==0 and optimizer_steps(initial)==optimizer_steps(bc)==0
    for name,value in initial.policy.state_dict().items():
        if name=='log_std':assert torch.equal(value,torch.full_like(value,-2.5))
        else:assert torch.equal(value,bc.policy.state_dict()[name]),('Initial BC mean/critic changed',name)
    model=PPO.load(folder/'policy.zip',device='cpu');updates=optimizer_steps(model)
    assert model.num_timesteps==65536 and updates==m['optimizer_steps'] and model._n_updates==m['sb3_epoch_counter']
    path=folder/'training.jsonl';assert sha(path)==m['trace_sha256']
    episode=-1;count=0;selected=0;failures=0;prior=None;rng=np.random.default_rng(seed)
    for line in path.open():
        row=json.loads(line);case=row['case'];now=row['time_s'];tick=row['tick']
        if row['episode_id']!=episode:
            assert tick==0 and row['episode_id']==episode+1;episode=row['episode_id']
            assert case==curriculum(rng),'Curriculum RNG/case sequence changed'
            c,clock,state,npcs,_=setup(case,'deterministic',Controller,PARAMS,grid=True)
            shadow,sclock,sego,_,_=setup(case,'deterministic',Base,PARAMS,grid=True)
            prior=None;last=np.zeros(8);sequence=0;previous=Command();shadow_previous=Command()
        clock.now=now;sclock.now=now;assert now==tick*.05
        np.testing.assert_allclose(row['state_before'],state,rtol=0,atol=1e-12)
        np.testing.assert_allclose(row['shadow_before'],sego,rtol=0,atol=1e-12)
        ingest(c,now,state,npcs);ingest(shadow,now,sego,npcs);c.update_model()
        equal(row['stiffness_estimate'],c.stiffness_estimate);equal(row['stiffness_uncertainty'],c.stiffness_uncertainty)
        if prior is not None:assert c.accept_plan(prior,now)
        issued_before=c.issued
        if row.get('sequence_plan_selected'):admitted(c,row,now,prior,issued_before);selected+=1
        c.supervisor.state=row['risk'];actual=Command(row['issued_steering'],row['issued_accel'])
        assert abs(actual.steering-issued_before.steering)<=.03+1e-12 and abs(actual.steering)<=.5 and -6<=actual.accel<=2.5
        c.pending.append((now+case['delay'],actual));c.issued=actual
        obs,valid=features(c,now,last);assert valid
        np.testing.assert_allclose(row['observation'],obs,rtol=0,atol=1e-7)
        action=np.asarray(row['label']);assert action.shape==(8,) and np.isfinite(action).all() and max(abs(action))<=1
        bonus=shaping(c,now,action);equal(row['shaping_reward'],bonus)
        sequence+=1;prior=PlanProposal(sequence,now,now,now,tuple(action));last=action
        expected=advance(state,Command(row['applied_steering'],row['applied_accel']),.05,case['stiffness'])
        state=c.apply(now,state,case['stiffness']);np.testing.assert_allclose(state,expected,rtol=0,atol=1e-12)
        np.testing.assert_allclose(row['state_after'],state,rtol=0,atol=1e-12)
        assert c.applied==Command(row['applied_steering'],row['applied_accel'])
        shadow.decide(now);sego=shadow.apply(now,sego,case['stiffness'])
        assert shadow.applied==Command(row['shadow_steering'],row['shadow_accel'])
        np.testing.assert_allclose(row['shadow_after'],sego,rtol=0,atol=1e-12)
        move_npcs(npcs,.05,c.route,case['scenario'])
        for name,state_npc in npcs.items():np.testing.assert_allclose(row['npc_truth'][name],state_npc,rtol=0,atol=1e-12)
        truth=truth_metrics(state,npcs,c.route,c.cfg);st=truth_metrics(sego,npcs,c.route,c.cfg)
        for name,value in truth.items():equal(row[name],value)
        for name,value in st.items():equal(row['shadow_truth'][name],value)
        rate=(c.applied.steering-previous.steering)/.05;srate=(shadow.applied.steering-shadow_previous.steering)/.05
        equal(row['steering_rate'],rate);equal(row['shadow_rate'],srate)
        def cost(t,r,u):return 8*t['error']**2+4*t['heading_error']**2+.04*r*r+.002*u.accel*u.accel
        ac=cost(truth,rate,c.applied);sc=cost(st,srate,shadow.applied)
        fail=bool(truth['collision'] or truth['corridor_exceeded']);reward=float(np.clip(1000*(sc-ac),-5,5)-20*fail)
        equal(row['actual_cost'],ac);equal(row['shadow_cost'],sc);equal(row['actual_reward'],reward);equal(row['reward'],reward+bonus)
        assert row['terminated']==fail and row['truncated']==(tick==119 and not fail)
        previous=c.applied;shadow_previous=shadow.applied;count+=1;failures+=fail
        if count%8192==0:print('REPLAYED EXPLORATION TRAINING',seed,count,'/65536',flush=True)
        if limit is not None and count>=limit:break
    assert count==(65536 if limit is None else limit)
    return dict(seed=seed,steps=count,adam_optimizer_steps=updates,sb3_epoch_counter=model._n_updates,
        independently_audited_plans=selected,failures=failures,shadow_controller_replayed=True)


def training_stage(seed):
    folder=DATA/f'policies/seed-{seed}';p=sources(folder)
    inputs={str(path.relative_to(ROOT)):sha(path) for path in folder.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    for name in p['source_hashes']:inputs[name]=sha(ROOT/name)
    inputs[str(Path(__file__).relative_to(ROOT))]=sha(__file__)
    cache=DATA/f'audits/training-{seed}-{sha(__file__)[:12]}.json'
    if cache.exists():
        cached=json.loads(cache.read_text());assert cached['input_hashes']==inputs
        assert cached['passed'] and cached['report']['steps']==65536
        print('SOURCE-PINNED TRAINING AUDIT REUSED',seed,flush=True);return cached['report']
    result=training_worker(seed)
    for name,digest in inputs.items():assert sha(ROOT/name)==digest,('Training audit input changed',name)
    cache.parent.mkdir(exist_ok=True);dump(cache,dict(passed=True,input_hashes=inputs,report=result))
    return result


def replay_record(meta):
    # Only the evidence root changes. The frozen v11 replay mathematics and
    # independent admission checker are reused verbatim, including the strict
    # expiry comparison against this cohort's own adaptive reference.
    old=frozen_audit.DATA;frozen_audit.DATA=DATA
    try:return frozen_audit.evaluate_record(meta)
    finally:frozen_audit.DATA=old


def statistics(records,assessment,p):
    lookup={(r['case']['id'],r['mode'],r['seed']):r for r in records};assert len(lookup)==1008
    metrics={}
    for mode in p['modes']:
        rr=[r for r in records if r['mode']==mode]
        metrics[mode]={key:float(np.mean([r[key] for r in rr])) for key in ('rmse_m','heading_rms','rate_rms','progress_m')}
        equal(assessment['metrics'][mode],metrics[mode]);assert assessment['failures'][mode]==sum(r['failed'] for r in rr)
    for mode in ('lqr','adaptive','scalar','bc','v11'):
        groups={};progress=[]
        for c in p['cases']:
            i=c['id'];ref=[lookup[(i,mode,s)] for s in ((0,) if mode in ('lqr','adaptive') else SEEDS)];pp=[lookup[(i,'ppo',s)] for s in SEEDS]
            groups.setdefault((c['scenario'],c['speed'],c['delay']),[]).append([np.mean([r['rmse_m'] for r in ref]),np.mean([r['rmse_m'] for r in pp])])
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in ref]) for r in pp)
        pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);avg=pairs.mean(axis=0)
        draw=np.random.default_rng(2134124).integers(36,size=(5000,36));sample=pairs[draw].mean(axis=1);a=assessment['comparisons'][mode]
        assert a['clusters']==36;equal(a['gain_percent'],100*(1-avg[1]/avg[0]))
        equal(a['ci95_percent'],np.quantile(100*(1-sample[:,1]/sample[:,0]),[.025,.975]).tolist())
        equal(a['heading_ratio'],metrics['ppo']['heading_rms']/metrics[mode]['heading_rms'])
        equal(a['rate_ratio'],metrics['ppo']['rate_rms']/metrics[mode]['rate_rms']);equal(a['minimum_progress_ratio'],min(progress))
    reasons=[]
    for seed in SEEDS:
        pp=[lookup[(c['id'],'ppo',seed)] for c in p['cases']];base=[lookup[(c['id'],'lqr',0)] for c in p['cases']]
        if any(r['failed'] for r in pp):reasons.append(f'actor_{seed}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(pp,base)):reasons.append(f'actor_{seed}_progress')
        for metric in ('heading_rms','rate_rms'):
            if np.mean([r[metric] for r in pp])>1.1*np.mean([r[metric] for r in base]):reasons.append(f'actor_{seed}_{metric}')
        equal(assessment['actors'][str(seed)],dict(mean_rmse_m=float(np.mean([r['rmse_m'] for r in pp])),failures=sum(r['failed'] for r in pp),
            selected_ticks=sum(r['selected_ticks'] for r in pp),gain_vs_adaptive_percent=float(100*(1-np.mean([r['rmse_m'] for r in pp])/metrics['adaptive']['rmse_m']))))
    if assessment['comparisons']['adaptive']['gain_percent']<10:reasons.append('requested_10_mean_gain')
    for mode in ('adaptive','bc','scalar','v11'):
        if assessment['comparisons'][mode]['ci95_percent'][0]<=0:reasons.append('confidence_'+mode)
    equal(assessment['reasons'],reasons);assert assessment['requested_10_passed']==(not reasons)
    assert assessment['adaptive_ci_lower_at_least_10']==(assessment['comparisons']['adaptive']['ci95_percent'][0]>=10)


def main():
    import torch
    from .evaluate import cases
    torch.set_num_threads(1);out=DATA/'evaluation';p=sources(out)
    assert p['cases']==cases() and p['bootstrap_seed']==2134124 and p['episodes']==1008
    records=json.loads((out/'summary.json').read_text());assert len(records)==1008
    inputs={str(Path(__file__).relative_to(ROOT)):sha(__file__)}
    for path in DATA.rglob('*'):
        if path.is_file() and path!=DATA/'verification.json' and '__pycache__' not in path.parts:
            inputs[str(path.relative_to(ROOT))]=sha(path)
            if path.name=='protocol.json':
                for name in json.loads(path.read_text()).get('source_hashes',{}):inputs[name]=sha(ROOT/name)
    for record in p['policies'].values():assert sha(ROOT/record['path'])==record['sha256'];inputs[record['path']]=record['sha256']
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        training=[f.result() for f in as_completed([pool.submit(training_stage,s) for s in SEEDS])]
    for path in (DATA/'audits').glob('*.json'):inputs[str(path.relative_to(ROOT))]=sha(path)
    print('VERIFIED ALL 196608 EXPLORATION PPO AND SHADOW TRANSITIONS',flush=True);audited=[]
    for record in records:assert record['case']==p['cases'][record['case']['id']]
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        for f in as_completed([pool.submit(replay_record,r) for r in records]):
            audited.append(f.result())
            if len(audited)%48==0:print('REPLAYED EXPLORATION EVALUATION',len(audited),'/1008',flush=True)
    assessment=json.loads((out/'assessment.json').read_text());statistics(records,assessment,p)
    for name,digest in inputs.items():assert sha(ROOT/name)==digest,('Audit input changed',name)
    report=dict(passed=True,training=sorted(training,key=lambda r:r['seed']),evaluation_episodes=1008,
        evaluation_ticks=sum(r['ticks'] for r in audited),independently_audited_eval_plans=sum(r['independently_audited_plans'] for r in audited),
        verifier_sha256=sha(__file__),input_hashes=inputs,stages=dict(training_steps=196608,evaluation_episodes=1008),
        all_requested_stages_verified=True,assessment_sha256=sha(out/'assessment.json'),
        limitation='Stochastic Adam trajectories not rerun; physics, full reward shadows, causal queries, every admitted robust plan and deterministic evaluation actions are replayed. Passing replay is distinct from performance promotion.')
    dump(DATA/'verification.json',report);print('ALL EXPLORATION STAGES INDEPENDENTLY VERIFIED',flush=True)


if __name__=='__main__':main()
