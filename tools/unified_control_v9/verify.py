"""Audit saved v9 evidence without selecting or rerunning experimental outcomes.

The replay shares the versioned plant and geometric definitions with the study;
it independently checks command FIFO, initial conditions, NPC movement, scores,
reward arithmetic, coverage and selection. It is not an independent simulator,
a proof of causality, a training optimizer replay, or a WCET proof.
"""
from pathlib import Path
import argparse, hashlib, io, json, math, os, zipfile
import numpy as np

from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command, Config, advance, errors
from integrations.unified_lans.simulation import initial, move_npcs, truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_campaign.study import StudyRoute

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/publication-v9'
SEEDS=(42,43,44)
MODES=('lqr','fixed','deterministic','optimized','adaptive','legacy_optimized','legacy_adaptive',
       'stanley','pure_pursuit','ppo','frozen_hybrid','hybrid','legacy_hybrid')
ACTOR_MODES=('ppo','frozen_hybrid','hybrid','legacy_hybrid')


def load(path):
    def reject(value):raise ValueError(('Nonfinite JSON token',value,path))
    return json.loads(Path(path).read_text(),parse_constant=reject)


def equal(actual,expected,context=''):
    """Structural equality, allowing only roundoff in recomputed finite numbers."""
    if isinstance(expected,dict):
        assert isinstance(actual,dict) and actual.keys()==expected.keys(),context
        for key in expected:equal(actual[key],expected[key],(context,key))
    elif isinstance(expected,(list,tuple)):
        assert isinstance(actual,(list,tuple)) and len(actual)==len(expected),context
        for i,(a,b) in enumerate(zip(actual,expected)):equal(a,b,(context,i))
    elif isinstance(expected,(float,np.floating)):
        assert actual is not None and math.isfinite(actual) and math.isfinite(expected),context
        assert math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12),(context,actual,expected)
    else:assert actual==expected,(context,actual,expected)


def source_check(directory):
    p=load(directory/'protocol.json')
    for name,digest in p.get('source_hashes',{}).items():
        assert sha(directory/'source'/name)==digest,('snapshot mismatch',name)
    # These functions are invoked for replay. Controller decisions are audited
    # from recorded commands rather than recreated using mutable live code.
    for name in ('integrations/unified_lans/physics.py','integrations/unified_lans/simulation.py',
                 'tools/unified_campaign/study.py','models/bicycle_model.py'):
        if name in p.get('source_hashes',{}):
            assert sha(ROOT/name)==p['source_hashes'][name],('replay dependency changed',name)
    return p


def fixture(case):
    route0,_,npcs=initial(case['scenario'],0.)
    route=StudyRoute(route0.kind,case['mirror'],case['phase'],case['amplitude'])
    y,h,_=route.geometry(0.)
    state=np.array([0.,y+case['lateral'],h+case['heading'],case['speed'],0.,0.])
    for npc in npcs.values():
        if case['scenario']=='crossing':npc[1]*=case['mirror'];npc[2]*=case['mirror']
        else:
            npc[1]=route.geometry(npc[0])[0] if case['scenario'] in ('curved','merge') else 0.
            npc[2]=route.geometry(npc[0])[1] if case['scenario']=='curved' else 0.
            npc[3]=max(3.,case['speed']-4.)
        npc[0]+=case.get('npc_x_shift',0.)
        npc[3]*=case.get('npc_speed_scale',1.)
    return route,state,npcs


class FIFO:
    def __init__(self,delay):
        self.delay=delay;self.queue=[];self.issued=Command();self.applied=Command()
    def step(self,now,issued,applied):
        assert abs(issued.steering-self.issued.steering)<=.03+1e-10
        assert abs(issued.steering)<=.5 and -6<=issued.accel<=2.5
        self.issued=issued;self.queue.append((now+self.delay,issued))
        while self.queue and self.queue[0][0]<=now+1e-9:_,self.applied=self.queue.pop(0)
        assert self.applied==applied,('actuator FIFO mismatch',now)


def decision_check(row):
    if row['source']=='ppo':
        assert 0<=row['proposal_age']<.15 and 0<=row['proposal_wall_age']<.15
        assert not row['ego_backup']
    if row.get('planned_candidate_selected') and 'planner_backend' in row:
        assert row['planner_used_request'] is not None
        assert 0<=row['planner_proposal_age']<.15 and 0<=row['planner_proposal_wall_age']<.15
        assert not row['planner_worker_failed']
    if row['ego_backup']:
        assert row['source'] in ('backup_lqr','hold_brake') and row['issued_accel']==-6.


def check_record(record,raw):
    assert sha(raw)==record['raw_sha256'],raw
    rows=[json.loads(line) for line in raw.read_text().splitlines()]
    assert len(rows)==record['ticks'] and 0<len(rows)<=record['expected_ticks']
    case=record['case'];route,state,npcs=fixture(case);fifo=FIFO(case['delay']);previous=Command()
    for i,row in enumerate(rows):
        assert i==row['tick'] and i*.05==row['time_s']
        np.testing.assert_allclose(state,row['state_before'],rtol=0,atol=1e-12)
        command=Command(row['applied_steering'],row['applied_accel'])
        fifo.step(row['time_s'],Command(row['issued_steering'],row['issued_accel']),command)
        state=advance(state,command,.05,case['stiffness'])
        np.testing.assert_allclose(state,row['state_after'],rtol=0,atol=1e-12)
        move_npcs(npcs,.05,route,case['scenario'])
        equal(row.get('npc_truth_after',row.get('npc_truth')),{k:v.tolist() for k,v in npcs.items()},raw)
        truth=clean(truth_metrics(state,npcs,route,Config()))
        for name,value in truth.items():equal(row[name],value,(raw,name))
        equal(row['steering_rate'],(command.steering-previous.steering)/.05,raw)
        decision_check(row);previous=command
    n=len(rows);expected=record['expected_ticks']
    values=dict(failed=n<expected or any(r['collision'] or abs(r['error'])>1.75 for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(expected-n)*2.5**2)/expected),
        heading_rms=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),
        rate_rms=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),progress_m=state[0],
        min_clearance=min(r['true_clearance'] for r in rows),collisions=sum(r['collision'] for r in rows),
        ppo_ticks=sum(r['source']=='ppo' for r in rows))
    for name,value in values.items():equal(record[name],value,(raw,name))
    return n


def calibration():
    root=DATA/'calibration';p=source_check(root);rr=load(root/'summary.json');ticks=0
    assert len(rr)==p['total_episodes']==576
    assert len({(r['candidate'],r['mode'],r['case']['id']) for r in rr})==576
    for r in rr:
        assert r['case']==p['cases'][r['case']['id']]
        raw=root/f'{r["candidate"]}-{r["mode"]}-{r["case"]["id"]:02d}.jsonl'
        assert r==load(raw.with_suffix('.json')) and r['protocol_sha256']==sha(root/'protocol.json')
        ticks+=check_record(r,raw)
    base={r['case']['id']:r for r in rr if r['candidate']=='lqr-h2'};assert len(base)==64
    scores=[]
    for c in p['candidates']:
        selected=[r for r in rr if r['candidate']==c['name']];assert len(selected)==128
        by_mode={}
        for mode in p['modes']:
            group=[r for r in selected if r['mode']==mode];assert len(group)==64
            by_mode[mode]={name:float(np.mean([r[field] for r in group])/np.mean([r[field] for r in base.values()]))
                for name,field in [('heading_ratio','heading_rms'),('rate_ratio','rate_rms')]}
        scores.append(dict(**c,failures=sum(r['failed'] for r in selected),
            heading_ratio=max(g['heading_ratio'] for g in by_mode.values()),rate_ratio=max(g['rate_ratio'] for g in by_mode.values()),
            minimum_progress_ratio=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in selected),
            mean_rmse_m=float(np.mean([r['rmse_m'] for r in selected])),by_mode=by_mode))
    stable=[s for s in scores if not s['sync'] and not s['failures'] and s['minimum_progress_ratio']>=.99-1e-12]
    strict=[s for s in stable if max(s['heading_ratio'],s['rate_ratio'])<=1.+1e-12]
    fallback=[s for s in stable if max(s['heading_ratio'],s['rate_ratio'])<=1.1+1e-12]
    eligible=strict or fallback
    selected=min(eligible,key=lambda s:(s['mean_rmse_m'],s['name'])) if eligible else None
    equal(load(root/'selection.json'),dict(selected=selected,scores=scores,no_quality_regression_passed=bool(strict),diagnostic_fallback=bool(not strict and fallback)))
    return dict(status='VERIFIED',episodes=576,ticks=ticks,selected=selected['name'] if selected else None)


def baselines():
    root=DATA/'baseline-calibration';p=source_check(root);rr=load(root/'summary.json');ticks=0
    assert len(rr)==p['total']==448
    assert len({(r['method'],r['parameter'],r['case']['id']) for r in rr})==448
    for r in rr:
        assert r['case']==p['cases'][r['case']['id']]
        raw=root/f'{r["method"]}-{r["parameter"]:g}-{r["case"]["id"]:02d}.jsonl'
        assert r==load(raw.with_suffix('.json')) and r['protocol_sha256']==sha(root/'protocol.json')
        ticks+=check_record(r,raw)
    base={r['case']['id']:r for r in rr if r['method']=='lqr'};assert len(base)==64
    scores=[];selected={}
    for method,parameters in p['candidates'].items():
        for parameter in parameters:
            group=[r for r in rr if r['method']==method and r['parameter']==parameter];assert len(group)==64
            scores.append(dict(method=method,parameter=parameter,failures=sum(r['failed'] for r in group),
                minimum_progress_ratio=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in group),
                mean_rmse_m=float(np.mean([r['rmse_m'] for r in group])),
                score=float(np.mean([r['rmse_m']+.1*r['heading_rms']+.01*r['rate_rms'] for r in group]))))
        eligible=[s for s in scores if s['method']==method and not s['failures'] and s['minimum_progress_ratio']>=.99]
        fallback=not eligible
        if fallback:eligible=[s for s in scores if s['method']==method]
        selected[method]=dict(**min(eligible,key=lambda s:(s['failures'],s['score'],s['parameter'])),diagnostic_fallback=fallback)
    equal(load(root/'selection.json'),dict(selected=selected,scores=scores))
    return dict(status='VERIFIED',episodes=448,ticks=ticks,diagnostic_fallbacks=[m for m,s in selected.items() if s['diagnostic_fallback']])


def optimizer_digest(state):
    digest=hashlib.sha256()
    def visit(value):
        if isinstance(value,dict):
            for key in sorted(value,key=str):digest.update(str(key).encode());visit(value[key])
        elif isinstance(value,(list,tuple)):
            for item in value:visit(item)
        elif hasattr(value,'detach'):
            array=value.detach().cpu().numpy();digest.update(str(array.dtype).encode());digest.update(str(array.shape).encode());digest.update(array.tobytes())
        else:digest.update(repr(value).encode())
    visit(state);return digest.hexdigest()


def training():
    import torch
    from .learning import training_case
    root=DATA/'policies';summary=load(root/'summary.json');assert [r['seed'] for r in summary]==list(SEEDS)
    output=[]
    for seed in SEEDS:
        folder=root/f'seed-{seed}';p=source_check(folder);m=load(folder/'manifest.json')
        assert m==summary[SEEDS.index(seed)] and m['seed']==p['seed']==seed
        assert m['new_steps']==p['new_steps']==16384 and m['steps']==49152
        assert m['no_endpoint_selection'] and not p['checkpoint_selection'] and p['service_s']==.05
        assert sha(folder/'protocol.json')==m['protocol_sha256'] and sha(folder/'policy.zip')==m['policy_sha256']
        assert sha(folder/'training.jsonl')==m['training_trace_sha256']
        assert sha(ROOT/'tools/unified_control_v9/learning.py')==p['source_hashes']['tools/unified_control_v9/learning.py']
        original=ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip'
        assert sha(original)==p['source_policy_sha256']==m['source_policy_sha256']
        with zipfile.ZipFile(original) as archive:
            old_steps=load_zip_data(archive)['num_timesteps']
            optimizer=torch.load(io.BytesIO(archive.read('policy.optimizer.pth')),map_location='cpu')
            assert optimizer_digest(optimizer)==m['source_optimizer_sha256'] and m['optimizer_restoration_verified']
        with zipfile.ZipFile(folder/'policy.zip') as archive:
            assert load_zip_data(archive)['num_timesteps']==old_steps+16384==49152
            assert optimizer_digest(torch.load(io.BytesIO(archive.read('policy.optimizer.pth')),map_location='cpu'))!=m['source_optimizer_sha256']
        assert {path.name for path in folder.glob('checkpoint-*.zip')}=={f'checkpoint-{n}.zip' for n in range(2048,16385,2048)}
        episode=-1;previous_row=None;steps=0;failures=0;ppo=0;reward_sum=0.;rng=np.random.default_rng(seed)
        with (folder/'training.jsonl').open() as stream:
            for line in stream:
                r=json.loads(line);case=r['case'];tick=r['tick'];info=r['info']
                if r['episode']!=episode:
                    assert r['episode']==episode+1 and tick==0
                    if previous_row is not None:assert previous_row['terminated'] or previous_row['truncated']
                    episode=r['episode'];assert case==training_case(rng)
                    route,state,npcs=fixture(case);shadow_state=state.copy();prev=Command();shadow_prev=Command()
                    fifo=FIFO(case['delay']);shadow_fifo=FIFO(case['delay']);sequence=0
                else:assert tick==previous_row['tick']+1 and case==previous_row['case']
                assert r['time_s']==tick*.05 and tick<120 and info['case']==case
                np.testing.assert_allclose(state,r['state_before'],rtol=0,atol=1e-12)
                np.testing.assert_allclose(shadow_state,r['shadow_before'],rtol=0,atol=1e-12)
                applied=Command(r['applied_steering'],r['applied_accel']);shadow=Command(r['shadow_steering'],r['shadow_accel'])
                issued=Command(r['issued_steering'],r['issued_accel']);d=r['decision'];sd=r['shadow_decision']
                assert issued==Command(d['issued_steering'],d['issued_accel'])
                fifo.step(r['time_s'],issued,applied);shadow_fifo.step(r['time_s'],Command(sd['issued_steering'],sd['issued_accel']),shadow)
                state=advance(state,applied,.05,case['stiffness']);shadow_state=advance(shadow_state,shadow,.05,case['stiffness'])
                np.testing.assert_allclose(state,r['state_after'],rtol=0,atol=1e-12)
                np.testing.assert_allclose(shadow_state,r['shadow_after'],rtol=0,atol=1e-12)
                move_npcs(npcs,.05,route,case['scenario']);equal(r['npc_truth'],{k:v.tolist() for k,v in npcs.items()})
                truth=truth_metrics(state,npcs,route,Config());shadow_truth=truth_metrics(shadow_state,npcs,route,Config())
                equal(r['truth'],clean(truth));equal(r['shadow_truth'],clean(shadow_truth))
                for key,value in truth.items():equal(info[key],clean(value),key)
                rate=(applied.steering-prev.steering)/.05;shadow_rate=(shadow.steering-shadow_prev.steering)/.05;w=p['reward']
                cost=lambda t,c,q:w['tracking']*t['error']**2+w['heading']*t['heading_error']**2+w['steering_rate']*q**2+w['acceleration']*c.accel**2
                actual_cost=cost(truth,applied,rate);shadow_cost=cost(shadow_truth,shadow,shadow_rate)
                heading_excess=max(0.,truth['heading_error']**2-shadow_truth['heading_error']**2);rate_excess=max(0.,rate**2-shadow_rate**2)
                failed=bool(truth['collision'] or abs(truth['error'])>1.75)
                reward=shadow_cost-actual_cost-w['excess_heading']*heading_excess-w['excess_rate']*rate_excess-w['failure']*failed
                for key,value in dict(actual_cost=actual_cost,shadow_cost=shadow_cost,heading_excess=heading_excess,rate_excess=rate_excess,steering_rate=rate,shadow_rate=shadow_rate,reward=reward).items():equal(info[key],value,key)
                equal(r['reward'],reward);assert r['terminated']==failed and r['truncated']==bool(tick==119 and not failed)
                assert np.isfinite(r['observation']).all() and len(r['observation'])==17 and np.max(np.abs(r['observation']))<=5.
                assert math.isfinite(r['action']) and -1<=r['action']<=1
                if info['submitted']:
                    sequence+=1;assert info['submission_sequence']==sequence
                else:assert info['submission_sequence'] is None
                if info['response_sequence'] is not None:assert info['response_sequence']==sequence
                decision_check(d);decision_check(sd)
                assert info['selected']==d['source']
                if case['delay']==.1:assert d['source']!='ppo'
                failures+=failed;ppo+=d['source']=='ppo';reward_sum+=reward;steps+=1
                previous_row=r;prev=applied;shadow_prev=shadow
        assert steps==16384
        interrupted=DATA/'interrupted-logging-attempt'/f'seed-{seed}';source_check(interrupted)
        assert (interrupted/'training.jsonl').stat().st_size==0 and not (interrupted/'manifest.json').exists()
        output.append(dict(seed=seed,steps=steps,episodes_started=episode+1,failures=failures,ppo_ticks=ppo,reward_sum=reward_sum,
            last_episode_complete=bool(previous_row['terminated'] or previous_row['truncated'])))
        print('VERIFIED training seed',seed,steps,'steps, shadow transitions and actual rewards',flush=True)
    return dict(status='VERIFIED',steps=49152,shadow_steps=49152,endpoints=output,interrupted_attempt_preserved=True,
        limitation='Saved optimizer origin/hash and final step count checked; stochastic optimizer updates are not rerun.')


def load_zip_data(archive):return json.loads(archive.read('data'))


def assessment(records):
    """Recompute every paired reference, stratified bootstrap and gate flags."""
    ids=sorted({r['case']['id'] for r in records});by={m:{} for m in MODES}
    for row in records:by[row['mode']].setdefault(row['case']['id'],[]).append(row)
    metrics={m:{key:float(np.mean([r[key] for rows in by[m].values() for r in rows]))
                for key in ('rmse_m','heading_rms','rate_rms','progress_m')} for m in MODES}
    comparisons={}
    for mode in MODES:
        if mode=='hybrid':continue
        groups={};progress=[]
        for i in ids:
            reference=by[mode][i];hybrid=by['hybrid'][i];case=reference[0]['case']
            key=(case['scenario'],int(case['speed']>=12),case['cluster_network'])
            groups.setdefault(key,[]).append((np.mean([r['rmse_m'] for r in reference]),np.mean([r['rmse_m'] for r in hybrid])))
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in reference]) for r in hybrid)
        pairs=np.asarray([np.mean(group,axis=0) for group in groups.values()]);mean=pairs.mean(axis=0)
        rng=np.random.default_rng(13913000);samples=pairs[rng.integers(len(pairs),size=(5000,len(pairs)))].mean(axis=1)
        comparisons[mode]=dict(gain_percent=float(100*(1-mean[1]/mean[0])),
            ci95_percent=np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist(),clusters=len(pairs),
            heading_ratio=metrics['hybrid']['heading_rms']/metrics[mode]['heading_rms'],
            rate_ratio=metrics['hybrid']['rate_rms']/metrics[mode]['rate_rms'],minimum_progress_ratio=float(min(progress)))
    reasons=[]
    for mode,target in [('lqr',5.),('optimized',1.)]:
        if comparisons[mode]['gain_percent']<target:reasons.append('mean_gain_'+mode)
        if comparisons[mode]['ci95_percent'][0]<=0:reasons.append('confidence_'+mode)
    for actor in SEEDS:
        hybrid=[next(r for r in by['hybrid'][i] if r['actor']==actor) for i in ids];base=[by['lqr'][i][0] for i in ids]
        if np.mean([r['rmse_m'] for r in hybrid])>=np.mean([r['rmse_m'] for r in base]):reasons.append(f'actor_{actor}_no_gain')
        for metric in ('heading_rms','rate_rms'):
            if np.mean([r[metric] for r in hybrid])>1.1*np.mean([r[metric] for r in base])+1e-12:reasons.append(f'actor_{actor}_{metric}')
        if any(r['failed'] for r in hybrid):reasons.append(f'actor_{actor}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(hybrid,base)):reasons.append(f'actor_{actor}_progress')
    return dict(metrics=metrics,comparisons=comparisons,original_gate_passed=not reasons,reasons=reasons,
        no_quality_regression=all(comparisons['lqr'][key]<=1.+1e-12 for key in ('heading_ratio','rate_ratio')),
        requested_30_all_references=not reasons and all(c['gain_percent']>=30 for c in comparisons.values()),
        ci_lower_30_all_references=not reasons and all(c['ci95_percent'][0]>=30 for c in comparisons.values()),
        failures={m:sum(r['failed'] for r in records if r['mode']==m) for m in MODES})


def confirmation():
    root=DATA/'confirmation';p=source_check(root);total=0;ticks=0;stages={}
    assert p['total_episodes']==2416 and p['final_once_no_tuning'] and p['seconds']==6.
    assert p['modes']==list(MODES) and p['seeds']==list(SEEDS)
    assert set(p['models'])=={f'{family}-{seed}' for family in ('old','new') for seed in SEEDS}
    assert set(p['cases'])=={'regression-development','regression-stress','development','stress','final'}
    for label,digest in p['models'].items():
        family,seed=label.split('-');directory='python-campaign-v2' if family=='old' else 'publication-v9'
        assert sha(ROOT/f'results/{directory}/policies/seed-{seed}/policy.zip')==digest
    assert p['selection_sha256']==sha(DATA/'calibration/selection.json')
    selected=load(DATA/'calibration/selection.json')['selected']
    equal(p['selected'],dict(quality_factor=selected['quality_factor'],guard_factor=selected['guard_factor'],
        nominal_feedback=selected['nominal_feedback'],early_id=True,tracking_only=False,planner_backend='logical'))
    equal(p['geometric'],load(DATA/'baseline-calibration/selection.json')['selected'])
    # Fixture generation is frozen independently of controller selection/training.
    from .campaign import cases
    for stage,expected in [('regression-development',160),('regression-stress',120),('development',672),('stress',120),('final',1344)]:
        fixtures=p['cases'][stage];assert fixtures==cases(stage)
        rr=load(root/f'{stage}_summary.json');assert len(rr)==expected
        modes=MODES if stage in ('development','final') else ('lqr','optimized','hybrid')
        wanted={(case['id'],mode,actor) for case in fixtures for mode in modes for actor in (SEEDS if mode in ACTOR_MODES else [0])}
        assert {(r['case']['id'],r['mode'],r['actor']) for r in rr}==wanted and len(wanted)==len(rr)
        for r in rr:
            assert r['case']==fixtures[r['case']['id']]
            raw=root/stage/f'{r["case"]["id"]:03d}-{r["mode"]}-{r["actor"]}.jsonl'
            assert r==load(raw.with_suffix('.json')) and r['protocol_sha256']==sha(root/'protocol.json')
            ticks+=check_record(r,raw);total+=1
        hybrid=[r for r in rr if r['mode']=='hybrid']
        stages[stage]=dict(episodes=expected,hybrid_failures=sum(r['failed'] for r in hybrid),hybrid_collisions=sum(r['collisions']>0 for r in hybrid))
        if stage in ('development','final'):
            result=assessment(rr);equal(load(root/f'{stage}_assessment.json'),result,stage)
            stages[stage].update(original_gate_passed=result['original_gate_passed'],requested_30_all_references=result['requested_30_all_references'],
                no_quality_regression=result['no_quality_regression'],lqr_gain_percent=result['comparisons']['lqr']['gain_percent'],
                adaptive_gain_percent=result['comparisons']['adaptive']['gain_percent'])
        print('VERIFIED',stage,expected,'episodes',flush=True)
    assert total==2416 and load(root/'STATUS.json')['final_once_complete']
    return dict(status='VERIFIED',episodes=total,ticks=ticks,stages=stages,
        limitation='Confidence intervals describe the declared finite distribution; passed integrity does not imply target attainment.')


def runtime():
    root=DATA/'live-functional';p=source_check(root);rr=load(root/'summary.json')
    assert p['selection_sha256']==sha(DATA/'calibration/selection.json')
    selected=load(DATA/'confirmation/protocol.json')['selected']
    jobs=[(role,seed,scenario,network,fault,'none') for role in ['old','new'] for seed in SEEDS
          for scenario,network,fault in [('following','nominal','none'),('curved','ego_blackout','none'),('merge','nominal','crash')]]
    jobs.extend([('new',42,'following','nominal','none',fault) for fault in ['stall','crash']])
    assert p['jobs']==[list(job) for job in jobs] and len(rr)==20 and p['deadline_ms']==50.
    totals={role:dict(checks=0,ticks=0,shortened_checks=0,response_misses=0,cycle_misses=0,
        scheduled_response_misses=0,scheduled_cycle_misses=0,collisions=0,corridor_exceedances=0) for role in ['old','new']}
    for result,job in zip(rr,jobs):
        role,seed,scenario,network,fault,planner_fault=job
        assert (result['role'],result['seed'],result['scenario'],result['planner_fault'])==(role,seed,scenario,planner_fault)
        directory=root/result['directory'];protocol=load(directory/'protocol.json');raw=directory/'ticks.jsonl'
        expected=load(directory/'summary.json');expected.update(role=role,seed=seed,scenario=scenario,planner_fault=planner_fault,directory=directory.name)
        assert result==expected and sha(raw)==result['raw_sha256']
        assert protocol['case']['network']==network and protocol['fault']==fault and protocol['planner_fault']==planner_fault
        assert protocol['source_hashes']==p['source_hashes']
        if role=='new':
            assert protocol['selected_kwargs']==selected and protocol['asynchronous_warm_responses']>0
        else:assert protocol['selected_kwargs'] is None and protocol['asynchronous_warm_responses'] is None
        family='python-campaign-v2' if role=='old' else 'publication-v9'
        assert protocol['policy_sha256']==sha(ROOT/f'results/{family}/policies/seed-{seed}/policy.zip')
        for name,digest in protocol['source_hashes'].items():assert sha(ROOT/name)==digest,('actual-worker source changed',name)
        rows=[json.loads(line) for line in raw.read_text().splitlines()]
        assert len(rows)==result['ticks']<=result['expected_ticks']==120 and rows
        case=protocol['case'];route,state,npcs=fixture(case);fifo=FIFO(case['delay']);previous=Command()
        for i,row in enumerate(rows):
            assert row['tick']==i and row['time_s']==i*.05
            np.testing.assert_allclose(state,row['state_before'],rtol=0,atol=1e-12)
            command=Command(row['applied_steering'],row['applied_accel'])
            fifo.step(row['time_s'],Command(row['issued_steering'],row['issued_accel']),command)
            state=advance(state,command,.05,case['stiffness']);np.testing.assert_allclose(state,row['state_after'],rtol=0,atol=1e-12)
            move_npcs(npcs,.05,route,case['scenario']);equal(row['npc_truth'],{k:v.tolist() for k,v in npcs.items()})
            for name,value in clean(truth_metrics(state,npcs,route,Config())).items():equal(row[name],value,(directory,name))
            equal(row['steering_rate'],(command.steering-previous.steering)/.05);previous=command;decision_check(row)
            assert math.isfinite(row['response_ms']) and math.isfinite(row['cycle_ms']) and 0<=row['response_ms']<=row['cycle_ms']
            equal(row['scheduled_release_offset_s'],row['time_s'])
            for key in ('actual_release_offset_s','release_lateness_ms','scheduled_response_ms','scheduled_cycle_ms'):
                assert math.isfinite(row[key]),(directory,key)
            assert math.isclose(row['release_lateness_ms'],1000*(row['actual_release_offset_s']-row['time_s']),
                rel_tol=0,abs_tol=1e-6),('release timestamp arithmetic',directory,i)
            assert row['scheduled_response_ms']+1e-6>=row['response_ms']+row['release_lateness_ms']
            assert row['scheduled_cycle_ms']+1e-6>=row['cycle_ms']+row['release_lateness_ms']
            assert row['scheduled_cycle_ms']>=row['scheduled_response_ms']
            if role=='new':assert row['planner_backend']=='process'
        recomputed=dict(response_misses=sum(r['response_ms']>50 for r in rows),cycle_misses=sum(r['cycle_ms']>50 for r in rows),
            scheduled_response_misses=sum(r['scheduled_response_ms']>50 for r in rows),
            scheduled_cycle_misses=sum(r['scheduled_cycle_ms']>50 for r in rows),
            scheduled_response_max_ms=max(r['scheduled_response_ms'] for r in rows),
            collisions=sum(r['collision'] for r in rows),corridor_exceedances=sum(r['corridor_exceeded'] for r in rows),
            max_error_m=max(abs(r['error']) for r in rows),response_max_ms=max(r['response_ms'] for r in rows),
            response_p95_ms=float(np.percentile([r['response_ms'] for r in rows],95)),ppo_ticks=sum(r['source']=='ppo' for r in rows))
        for name,value in recomputed.items():equal(result[name],value,(directory,name))
        totals[role]['checks']+=1;totals[role]['ticks']+=len(rows);totals[role]['shortened_checks']+=len(rows)<120
        for name in ('response_misses','cycle_misses','scheduled_response_misses','scheduled_cycle_misses','collisions','corridor_exceedances'):
            totals[role][name]+=recomputed[name]
    return dict(status='VERIFIED',checks=20,roles=totals,limitation='Finite observed timings only; no formal WCET guarantee or isolated architecture attribution.')


def native():
    """Check native sensor-coordinate consistency; never replay native ego with RK4."""
    root=DATA/'native';p=source_check(root);rr=load(root/'summary.json');status=load(root/'STATUS.json')
    assert not p['smoke'] and p['kind']=='fixed_native_single_vehicle_transfer' and p['webots']=='R2025a'
    assert len(p['cases'])==len(rr)==status['episodes']==16 and status['completed']
    assert status['full_framework_native_validated'] is False
    expected={(route,speed,mode,seed) for route in ('straight','sine') for speed in (8.,16.)
              for mode,seed in [('lqr',0),('hybrid',42),('hybrid',43),('hybrid',44)]}
    assert {(c['route'],c['speed'],c['mode'],c['seed']) for c in p['cases']}==expected
    safety=p['python_safety'];hybrid=[]
    assert safety['failed']==0 and safety['status_sha256']==sha(DATA/'confirmation/STATUS.json')
    for name,digest in safety['summary_sha256'].items():
        path=DATA/'confirmation'/name;assert sha(path)==digest
        hybrid.extend(r for r in load(path) if r['mode']=='hybrid')
    assert len(hybrid)==safety['episodes'] and all(not r['failed'] for r in hybrid)
    for seed,digest in p['policies'].items():assert sha(DATA/'policies'/f'seed-{seed}/policy.zip')==digest
    totals=dict(ticks=0,corridor_exceedances=0,shortened_episodes=0,response_misses=0,cycle_misses=0,
                scheduled_response_misses=0,scheduled_cycle_misses=0)
    outcomes=[]
    template=(root/'source/integrations/webots/worlds/publication_v9.wbt').read_text()
    calibration=load(root/'source/integrations/webots/research/calibration.json')
    for case,result in zip(p['cases'],rr):
        directory=root/case['name'];cfg=load(directory/'case.json');provenance=load(directory/'provenance.json')
        assert cfg==dict(case,output=str(directory)) and result['case']==cfg
        assert load(directory/'summary.json')==result
        assert provenance['native_physics'] and provenance['ego_python_integrated'] is False and provenance['physics_step_s']==.001
        world=template.replace('../.runtime/protos',str(ROOT/'integrations/webots/.runtime/protos'))
        for axle in ('front','rear'):
            slip=4*case['speed']/80000*calibration[axle+'_slip_multiplier']
            world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
        assert world==(directory/'generated-world.wbt').read_text()==(directory/'project/worlds/validation.wbt').read_text()
        assert sha(directory/'generated-world.wbt')==provenance['world_sha256']
        assert sha(directory/'case.json')==provenance['config_sha256']
        raw=directory/'ticks.jsonl';assert sha(raw)==result['raw_sha256']==provenance['raw_sha256']
        rows=[json.loads(line) for line in raw.read_text().splitlines()]
        frame=load(directory/'map-frame.json');vehicle=load(directory/'vehicle.json')
        assert frame['physical_pose_changed'] is False and vehicle['physics_step_s']==.001 and vehicle['control_period_s']==.05
        assert vehicle['nominal_total_mass_kg']==1650 and vehicle['nominal_total_cg_x_m']==1.4 and vehicle['nominal_total_yaw_inertia']==4224
        route=StudyRoute(case['route'],1,case['phase'],case['amplitude'])
        angle=frame['angle_rad'];rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
        def mapped(value):
            state=np.asarray(value,float).copy()
            state[:2]=rotation@(state[:2]-np.asarray(frame['origin_world_cg_m']))+np.asarray(frame['offset_map_m'])
            state[2]=math.atan2(math.sin(state[2]+angle),math.cos(state[2]+angle))
            return state
        assert 0<len(rows)==result['ticks']<=result['expected_ticks']==120
        np.testing.assert_allclose(vehicle['initial_map_state'],rows[0]['state_before'],rtol=0,atol=1e-12)
        assert abs(rows[0]['state_before'][0])<1e-12
        y,h,_=route.geometry(0.)
        equal(rows[0]['state_before'][1],y+case['lateral']);equal(rows[0]['state_before'][2],h+case['heading'])
        equal(rows[0]['state_before'][3],vehicle['measured_warmup_speed_m_s'])
        previous=Command();fifo=FIFO(0.);previous_row=None;actuator=0.
        for i,row in enumerate(rows):
            assert row['tick']==i and row['time_s']==i*.05 and row['collision_assessed'] is False
            for when in ('before','after'):
                np.testing.assert_allclose(mapped(row['world_state_'+when]),row['state_'+when],rtol=0,atol=1e-12)
            if previous_row is not None:
                np.testing.assert_allclose(previous_row['world_state_after'],row['world_state_before'],rtol=0,atol=1e-12)
                equal(row['measured_steering_before'],previous_row['measured_steering_after'])
            assert abs(row['sim_time_after_s']-row['sim_time_before_s']-.05)<1e-8
            command=Command(row['applied_steering'],row['applied_accel'])
            fifo.step(row['time_s'],Command(row['issued_steering'],row['issued_accel']),command)
            equal(row['steering_rate'],(command.steering-previous.steering)/.05)
            equal(row['actuator_before'],actuator)
            for _ in range(50):actuator=float(np.clip(command.steering,actuator-.0006,actuator+.0006))
            equal(row['actuator_after'],actuator)
            assert abs(actuator)<=.5+1e-12 and 0<=row['max_actuator_rate']<=.6+1e-9
            assert row['max_actuator_rate']+1e-9>=abs(row['actuator_after']-row['actuator_before'])/.05
            assert math.isfinite(row['max_measured_rate']) and row['max_measured_rate']>=0
            equal(row['cruise_target_m_s'],float(np.clip(row['state_before'][3]+command.accel*.05,0.,case['speed'])))
            e,_=errors(np.asarray(row['state_after']),route)
            equal(row['error'],float(e[0]));equal(row['heading_error'],float(e[2]))
            assert row['corridor_exceeded']==bool(abs(e[0])>1.75)
            assert 0<=row['response_ms']<=row['cycle_ms']
            decision_check(row);previous=command;previous_row=row
        n=len(rows)
        metrics=dict(completed=n==120,rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
            heading_rmse_rad=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
            steering_rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),
            corridor_exceedances=sum(r['corridor_exceeded'] for r in rows),max_error_m=max(abs(r['error']) for r in rows),
            progress_m=rows[-1]['state_after'][0],response_misses=sum(r['response_ms']>50 for r in rows),
            cycle_misses=sum(r['cycle_ms']>50 for r in rows),scheduled_response_misses=sum(r['scheduled_response_ms']>50 for r in rows),
            scheduled_cycle_misses=sum(r['wall_schedule_lateness_ms']>0 for r in rows),
            response_max_ms=max(r['response_ms'] for r in rows),cycle_max_ms=max(r['cycle_ms'] for r in rows),
            ppo_ticks=sum(r['source']=='ppo' for r in rows),mpc_ticks=sum(bool(r.get('planned_candidate_selected')) for r in rows),
            max_command_rate=max(abs(r['steering_rate']) for r in rows),max_actuator_rate=max(r['max_actuator_rate'] for r in rows),
            max_measured_rate=max(r['max_measured_rate'] for r in rows))
        for name,value in metrics.items():equal(result[name],value,(directory,name))
        assert result['failure']==('tracking_envelope' if any(abs(r['error'])>2.5 for r in rows) else None)
        totals['ticks']+=n;totals['shortened_episodes']+=n<120
        for name in ('corridor_exceedances','response_misses','cycle_misses','scheduled_response_misses','scheduled_cycle_misses'):totals[name]+=metrics[name]
        outcomes.append(dict(case=case['name'],rmse_m=metrics['rmse_m'],corridor_exceedances=metrics['corridor_exceedances'],ticks=n))
    assert status['all_tracking_completed']==all(r['completed'] and r['corridor_exceedances']==0 for r in rr)
    return dict(status='VERIFIED',episodes=16,totals=totals,outcomes=outcomes,
        limitation='Sensor/frame/command/metric and generated-world consistency only. Native dynamics and within-tick measured wheel-rate maxima are not replayed; traffic/collisions unassessed.')


def audit_inputs(requested):
    """Pin evidence and imported replay/source bytes, without following symlinks.

    A complete before/after comparison prevents changed evidence from inheriting
    a stale successful audit when the evidence package is sealed afterwards.
    Output reports are outside these input directories and are not self-hashed.
    """
    directories={'calibration':['calibration'],'baselines':['baseline-calibration'],
        'training':['policies','interrupted-logging-attempt'],'confirmation':['confirmation'],
        'runtime':['live-functional'],'native':['native']}
    paths={Path(__file__)}
    for stage in requested:
        for name in directories[stage]:
            start=DATA/name
            if not start.exists():continue
            for folder,subdirs,filenames in os.walk(start,followlinks=False):
                base=Path(folder)
                subdirs[:]=[n for n in subdirs if not (base/n).is_symlink() and n not in ('__pycache__','.pytest_cache')]
                for filename in filenames:
                    path=base/filename
                    if path.is_symlink() or path.suffix in ('.pyc','.pyo','.nbc','.nbi'):continue
                    assert path.is_file(),path
                    paths.add(path)
                    if filename=='protocol.json':
                        for source in load(path).get('source_hashes',{}):
                            relative=Path(source)
                            assert not relative.is_absolute() and '..' not in relative.parts,source
                            active=ROOT/relative
                            if active.exists():
                                assert active.is_file() and not active.is_symlink(),active
                                paths.add(active)
    # Fixed historical policies are audited directly, not copied into v9 data.
    if any(stage in requested for stage in ('training','confirmation','runtime')):
        paths.update(ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip' for seed in SEEDS)
    if any(stage in requested for stage in ('confirmation','runtime','native')):
        dependency_names=['calibration/selection.json','baseline-calibration/selection.json',
            'confirmation/protocol.json','confirmation/STATUS.json']
        dependency_names.extend(f'confirmation/{stage}_summary.json' for stage in
            ('regression-development','regression-stress','development','stress','final'))
        dependency_names.extend(f'policies/seed-{seed}/policy.zip' for seed in SEEDS)
        paths.update(DATA/name for name in dependency_names if (DATA/name).is_file())
    result={}
    for path in sorted(paths):
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
        result[str(path.relative_to(ROOT))]=digest.hexdigest()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['all','calibration','baselines','training','confirmation','runtime','native'],default='all')
    parser.add_argument('--allow-incomplete',action='store_true',help='Label missing future stages NOT_RUN instead of failing.')
    parser.add_argument('--output',type=Path,help='Write the technical audit JSON after all requested checks finish.')
    args=parser.parse_args();report={}
    stages={'calibration':calibration,'baselines':baselines,'training':training,'confirmation':confirmation,'runtime':runtime,'native':native}
    sentinels={'calibration':'calibration/selection.json','baselines':'baseline-calibration/selection.json',
        'training':'policies/summary.json','confirmation':'confirmation/STATUS.json','runtime':'live-functional/summary.json','native':'native/STATUS.json'}
    requested=[name for name in stages if args.stage in ('all',name)]
    inputs=audit_inputs(requested)
    for name,function in stages.items():
        if args.stage not in ('all',name):continue
        if not (DATA/sentinels[name]).exists() and args.allow_incomplete:report[name]=dict(status='NOT_RUN')
        else:report[name]=function()
        print(name,json.dumps(report[name]),flush=True)
    assert inputs==audit_inputs(requested),'Audit inputs changed during verification; do not seal a stale audit'
    result=dict(verifier_sha256=sha(Path(__file__)),input_hashes=inputs,
        all_requested_stages_verified=all(r['status']=='VERIFIED' for r in report.values()),stages=report,
        proof_scope='Integrity of saved evidence and declared finite arithmetic, not guaranteed superiority or publication readiness.')
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('AUDIT COMPLETE',result['all_requested_stages_verified'],flush=True)


if __name__=='__main__':main()
