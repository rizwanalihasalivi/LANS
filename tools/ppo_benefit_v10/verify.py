"""Independent command/plant/reward/whole-run audit of saved PPO evidence."""
from pathlib import Path
import argparse,ast,json,math
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,advance
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from tools.unified_control_v9.verify import fixture,FIFO,decision_check,equal
from .core import ROOT,DATA,dump


def check_sources(folder):
    p=json.loads((folder/'protocol.json').read_text())
    for name,digest in p['source_hashes'].items():
        assert sha(folder/'source'/name)==digest,('Snapshot changed',name)
        # Audit tooling can be repaired independently of frozen execution code.
        if folder.name=='teacher' and name=='tools/ppo_benefit_v10/train.py':
            def collector(path):return next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='collect')
            assert ast.dump(collector(folder/'source'/name))==ast.dump(collector(ROOT/name))
        elif name.startswith('tools/ppo_benefit_v10/') and name!='tools/ppo_benefit_v10/core.py':
            pass  # Drivers/verifiers are snapshotted, not invoked for plant replay.
        else:
            assert sha(ROOT/name)==digest,('Replay dependency changed',name)
    return p


def transition(row,route,state,npcs,fifo):
    np.testing.assert_allclose(row['state_before'],state,rtol=0,atol=1e-12)
    decision=row.get('decision',row);decision_check(decision)
    command=Command(row['applied_steering'],row['applied_accel'])
    fifo.step(row['time_s'],Command(decision['issued_steering'],decision['issued_accel']),command)
    assert abs(command.steering)<=.5+1e-12 and -6<=command.accel<=2.5
    state=advance(state,command,.05,row['case']['stiffness'])
    np.testing.assert_allclose(row['state_after'],state,rtol=0,atol=1e-12)
    move_npcs(npcs,.05,route,row['case']['scenario'])
    for name,z in npcs.items():np.testing.assert_allclose(row['npc_truth'][name],z,rtol=0,atol=1e-12)
    from integrations.unified_lans.physics import Config
    truth=truth_metrics(state,npcs,route,Config(horizon=2.))
    for key,value in truth.items():equal(row.get('truth',row)[key],value,(key,row['time_s']))
    return state,truth


def training_trace(path,expected=None,dataset=None):
    episode=-1;rows=0;failures=0;ppo=0;label_index=0;prev=None;shadow_previous=Command();query_action=None
    labels=None if dataset is None else np.load(dataset)
    for line in path.open():
        row=json.loads(line);case=row['case'];tick=row['tick'];now=row['time_s']
        if row['episode']!=episode:
            assert tick==0;episode=row['episode'];route,state,npcs=fixture(case);shadow_state=state.copy()
            fifo=FIFO(case['delay']);sfifo=FIFO(case['delay']);shadow_previous=Command();prev=None;query_action=None
        assert now==tick*.05
        if prev is not None:assert tick==prev['tick']+1 and prev['case']==case
        if dataset is not None:
            assert abs(row['action']-float(labels['actions'][label_index,0]))<1e-7
            if prev is not None:np.testing.assert_allclose(labels['observations'][label_index],prev['observation_next'],rtol=0,atol=0)
            label_index+=1
        old_command=fifo.applied
        state,truth=transition(row,route,state,npcs,fifo)
        rate=(fifo.applied.steering-old_command.steering)/.05;equal(row['steering_rate'],rate)
        np.testing.assert_allclose(row['shadow_before'],shadow_state,rtol=0,atol=1e-12)
        sd=row['shadow_decision'];sc=Command(row['shadow_steering'],row['shadow_accel']);decision_check(sd)
        sfifo.step(now,Command(sd['issued_steering'],sd['issued_accel']),sc)
        shadow_state=advance(shadow_state,sc,.05,case['stiffness'])
        np.testing.assert_allclose(row['shadow_after'],shadow_state,rtol=0,atol=1e-12)
        from integrations.unified_lans.physics import Config
        st=truth_metrics(shadow_state,npcs,route,Config(horizon=2.))
        for key,value in st.items():equal(row['shadow_truth'][key],value)
        srate=(sc.steering-shadow_previous.steering)/.05;equal(row['shadow_rate'],srate)
        def cost(t,r,u):return 8*t['error']**2+4*t['heading_error']**2+.04*r**2+.002*u.accel**2
        ac=cost(truth,rate,fifo.applied);bc=cost(st,srate,sc)
        d=row['decision'];alternatives=[v for k,v in d['costs'].items() if k!='ppo' and d['eligible'].get(k,False)]
        bonus=0.
        if d['source']=='ppo':
            assert query_action is not None
            equal(d['residual'],float(np.clip(query_action,-1,1))*.08)
            if alternatives:
                reference=min(alternatives);bonus=float(np.clip((reference-d['costs']['ppo'])/max(abs(reference),1e-8),0,1))
        fail=bool(truth['collision'] or truth['corridor_exceeded']);reward=float(np.clip(1000*(bc-ac),-5,5)+bonus-20*fail)
        equal(row['reward'],reward);equal(row['actual_cost'],ac);equal(row['shadow_cost'],bc);equal(row['incremental_reward'],bonus)
        assert row['terminated']==fail and row['truncated']==(tick>=119 and not fail)
        obs=np.asarray(row['observation_next']);assert obs.shape==(30,) and np.isfinite(obs).all()
        if row['terminated'] or row['truncated']:assert not obs.any()
        else:
            equal(float(obs[20]),float(np.float32(np.clip(row['action'],-1,1))))
            assert row['response_accepted_after_step'] is True
        rows+=1;failures+=fail;ppo+=d['source']=='ppo';prev=row;shadow_previous=sc;query_action=row['action']
    if expected is not None:assert rows==expected
    if labels is not None:assert label_index==len(labels['actions'])
    return dict(steps=rows,failures=failures,ppo_ticks=ppo,trace_sha256=sha(path))


def evaluation(directory='evaluation',expected=864):
    out=DATA/directory;p=check_sources(out)
    for key,record in p['policies'].items():
        if isinstance(record,dict):assert sha(ROOT/record['path'])==record['sha256']
        else:assert sha(DATA/f'{p.get("policy_directory","policies-anchor")}/seed-{key}/policy.zip')==record
    records=json.loads((out/'summary.json').read_text());assert len(records)==expected
    lookup={};ticks=0
    for record in records:
        case=record['case'];key=(case['id'],record['mode'],record['seed']);assert key not in lookup;lookup[key]=record
        assert case==p['cases'][case['id']]
        path=out/f'{case["id"]:03d}-{record["mode"]}-{record["seed"]}.jsonl'
        assert sha(path)==record['raw_sha256'] and record['protocol_sha256']==sha(out/'protocol.json')
        equal(json.loads(path.with_suffix('.json').read_text()),record)
        route,state,npcs=fixture(case);fifo=FIFO(case['delay']);rows=[];last=None
        for i,line in enumerate(path.open()):
            row=json.loads(line);row['case']=case
            assert row['tick']==i and row['time_s']==i*.05
            previous=fifo.applied;state,truth=transition(row,route,state,npcs,fifo)
            equal(row['steering_rate'],(fifo.applied.steering-previous.steering)/.05)
            obs=np.asarray(row['observation_after_issue']);assert obs.shape==(30,) and np.isfinite(obs).all()
            if row['source']=='ppo':
                assert last is not None;equal(row['residual'],last*.08)
            last=row['submitted_action'];rows.append(row)
        n=len(rows);assert n==record['ticks'] and 0<n<=120
        if n<120:assert rows[-1]['collision'] or abs(rows[-1]['error'])>2.5
        recomputed=dict(failed=n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),
            rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
            heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
            rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(state[0]),
            collisions=sum(r['collision'] for r in rows),ppo_ticks=sum(r['source']=='ppo' for r in rows),
            ppo_evaluated=sum('ppo' in r['eligible'] for r in rows))
        for name,value in recomputed.items():equal(record[name],value)
        if abs(case['delay']-.1)<1e-10:
            # Fixed 50 ms service + 100 ms queue reaches the strict TTL. Every
            # neural/teacher path must exactly retain the analytical commands.
            reference_path=DATA/f'evaluation/{case["id"]:03d}-adaptive-0.jsonl'
            reference_rows=[json.loads(line) for line in reference_path.open()]
            assert not any(r['source']=='ppo' for r in rows)
            np.testing.assert_allclose([[r['applied_steering'],r['applied_accel']] for r in rows],
                [[r['applied_steering'],r['applied_accel']] for r in reference_rows],rtol=0,atol=1e-12)
        ticks+=n
    result=dict(episodes=expected,ticks=ticks,failures={mode:sum(r['failed'] for r in records if r['mode']==mode) for mode in {r['mode'] for r in records}})
    assessment=json.loads((out/'assessment.json').read_text())
    if expected==216:
        assert set(lookup)=={(case['id'],'ppo',seed) for case in p['cases'] for seed in (42,43,44)}
        reference=json.loads((DATA/'evaluation/summary.json').read_text())
        assert p['reference_summary_sha256']==sha(DATA/'evaluation/summary.json')
        records=[r for r in reference if r['mode']!='ppo']+records
        lookup={(r['case']['id'],r['mode'],r['seed']):r for r in records}
    # Independently rebuild every paired stratum distribution and confidence interval.
    for mode in ('lqr','adaptive','teacher','old','bc'):
        clusters={}
        for case in p['cases']:
            i=case['id'];r=[lookup[(i,mode,s)]['rmse_m'] for s in ((42,43,44) if mode in ('old','bc') else [0])]
            h=[lookup[(i,'ppo',s)]['rmse_m'] for s in (42,43,44)]
            group=(case['scenario'],case['speed'],case['delay']);clusters.setdefault(group,[]).append([np.mean(r),np.mean(h)])
        values=np.asarray([np.mean(v,axis=0) for v in clusters.values()]);avg=values.mean(axis=0)
        gain=float(100*(1-avg[1]/avg[0]));equal(assessment['comparisons'][mode]['gain_percent'],gain)
        draws=np.random.default_rng(991124).integers(36,size=(5000,36));samples=values[draws].mean(axis=1)
        equal(assessment['comparisons'][mode]['ci95_percent'],np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist())
    for mode in ('lqr','adaptive','teacher','old','bc','ppo'):
        rr=[r for r in records if r['mode']==mode]
        for metric in ('rmse_m','heading_rms','rate_rms','progress_m'):
            equal(assessment['metrics'][mode][metric],float(np.mean([r[metric] for r in rr])))
    reasons=[]
    for seed in (42,43,44):
        pp=[lookup[(case['id'],'ppo',seed)] for case in p['cases']];base=[lookup[(case['id'],'lqr',0)] for case in p['cases']]
        if any(r['failed'] for r in pp):reasons.append(f'actor_{seed}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(pp,base)):reasons.append(f'actor_{seed}_progress')
        for metric in ('heading_rms','rate_rms'):
            if np.mean([r[metric] for r in pp])>1.1*np.mean([r[metric] for r in base]):reasons.append(f'actor_{seed}_{metric}')
    for mode in ('adaptive','old'):
        if assessment['comparisons'][mode]['ci95_percent'][0]<=0:reasons.append('confidence_'+mode)
    equal(assessment['reasons'],reasons);assert assessment['primary_success']==(not reasons)
    assert assessment['ppo_finetuning_positive']==(assessment['comparisons']['bc']['ci95_percent'][0]>0)
    if expected==216:
        original={(r['case']['id'],r['seed']):r for r in reference if r['mode']=='ppo'};groups={}
        for case in p['cases']:
            i=case['id'];groups.setdefault((case['scenario'],case['speed'],case['delay']),[]).append([
                np.mean([original[(i,s)]['rmse_m'] for s in (42,43,44)]),np.mean([lookup[(i,'ppo',s)]['rmse_m'] for s in (42,43,44)])])
        pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);avg=pairs.mean(axis=0)
        draws=np.random.default_rng(991124).integers(36,size=(5000,36));samples=pairs[draws].mean(axis=1)
        equal(assessment['comparisons']['unregularized_ppo']['gain_percent'],float(100*(1-avg[1]/avg[0])))
        equal(assessment['comparisons']['unregularized_ppo']['ci95_percent'],np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist())
    result['compared_gains']={k:v['gain_percent'] for k,v in assessment['comparisons'].items()}
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--training-only',action='store_true');args=parser.parse_args()
    anchor_complete=(DATA/'policies-anchor/summary.json').exists()
    before={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))}
    for path in DATA.rglob('*'):
        if not anchor_complete and 'policies-anchor' in path.relative_to(DATA).parts:continue
        if path.is_file() and path.name!='verification.json' and '__pycache__' not in path.parts:
            before[str(path.relative_to(ROOT))]=sha(path)
            if path.name=='protocol.json':
                for name in json.loads(path.read_text()).get('source_hashes',{}):
                    if (ROOT/name).is_file():before[name]=sha(ROOT/name)
    folder=DATA/'teacher';p=check_sources(folder);m=json.loads((folder/'manifest.json').read_text())
    assert sha(folder/'dataset.npz')==m['dataset_sha256'];teacher_result=training_trace(folder/'transitions.jsonl',m['samples'],folder/'dataset.npz')
    assert teacher_result['failures']==m['failures']
    policies=[]
    for seed in (42,43,44):
        folder=DATA/f'policies/seed-{seed}';p=check_sources(folder);m=json.loads((folder/'manifest.json').read_text())
        assert m['steps']==16384 and sha(folder/'policy.zip')==m['policy_sha256'] and sha(folder/'bc-policy.zip')==m['bc_policy_sha256']
        result=training_trace(folder/'training.jsonl',16384);assert result['trace_sha256']==m['trace_sha256']
        policies.append(dict(seed=seed,**result));print('VERIFIED PPO TRAINING',seed,flush=True)
    interrupted=[]
    for seed in (42,43,44):
        path=DATA/f'interrupted-info-attempt/seed-{seed}/training.jsonl'
        if path.exists():interrupted.append(dict(seed=seed,**training_trace(path,1024)))
        empty=DATA/f'interrupted-shape-attempt/seed-{seed}/training.jsonl'
        assert empty.exists() and empty.stat().st_size==0
    report=dict(teacher=teacher_result,training=policies,interrupted_rollouts=interrupted)
    if not args.training_only:report['evaluation']=evaluation()
    if anchor_complete:
        anchored=[]
        for seed in (42,43,44):
            folder=DATA/f'policies-anchor/seed-{seed}';p=check_sources(folder);m=json.loads((folder/'manifest.json').read_text())
            assert m['steps']==16384 and sha(folder/'policy.zip')==m['policy_sha256']
            assert p['source_policy_sha256']==sha(DATA/f'policies/seed-{seed}/bc-policy.zip')
            losses=json.loads((folder/'anchor-loss.json').read_text());assert len(losses)==m['anchor_steps']==1280
            assert all(math.isfinite(x) and x>=0 for x in losses)
            r=training_trace(folder/'training.jsonl',16384);assert r['trace_sha256']==m['trace_sha256']
            anchored.append(dict(seed=seed,**r));print('VERIFIED ANCHORED PPO',seed,flush=True)
        report['anchored_training']=anchored
        if not args.training_only:report['anchored_evaluation']=evaluation('anchor-evaluation',216)
        controls=[]
        import torch
        from stable_baselines3 import PPO
        torch.set_num_threads(1);dataset=np.load(DATA/'teacher/dataset.npz')
        train_obs=torch.tensor(dataset['observations']);train_actions=torch.tensor(dataset['actions']);train_weights=torch.tensor(dataset['weights'])
        for seed in (42,43,44):
            folder=DATA/f'policies-continued-bc/seed-{seed}';p=check_sources(folder);m=json.loads((folder/'manifest.json').read_text())
            assert m['supervised_only'] and m['steps']==0 and m['supervised_updates']==1280
            assert sha(folder/'policy.zip')==m['policy_sha256']
            assert p['source_policy_sha256']==sha(DATA/f'policies/seed-{seed}/bc-policy.zip')
            losses=json.loads((folder/'loss.json').read_text());assert len(losses)==1280 and all(math.isfinite(x) and x>=0 for x in losses)
            replay=PPO.load(DATA/f'policies/seed-{seed}/bc-policy.zip',device='cpu');generator=np.random.default_rng(9000+seed)
            for step_index in range(1280):
                indices=generator.integers(len(train_obs),size=128);mean=replay.policy.get_distribution(train_obs[indices]).distribution.mean
                loss=.5*(train_weights[indices]*(mean-train_actions[indices]).square().mean(dim=1)).mean()
                equal(losses[step_index],float(loss.detach()))
                replay.policy.optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(replay.policy.parameters(),.5);replay.policy.optimizer.step()
            saved=PPO.load(folder/'policy.zip',device='cpu')
            for name,value in replay.policy.state_dict().items():torch.testing.assert_close(saved.policy.state_dict()[name],value,rtol=0,atol=0)
            controls.append(dict(seed=seed,supervised_updates=1280,ppo_steps=0,weights_reproduced_exactly=True))
        report['continued_bc_training']=controls
        if not args.training_only:report['continued_bc_evaluation']=evaluation('continued-bc-evaluation',216)
    else:report['pending_arms']=['teacher_anchored_ppo']
    for name,digest in before.items():assert sha(ROOT/name)==digest,('Audit input changed',name)
    report.update(stages=dict(report),verifier_sha256=sha(Path(__file__)),input_hashes=before,
        all_requested_checks_passed=True,all_requested_stages_verified=True,
        limitation='Physics, FIFO, metrics, delayed-action associations, rewards, hashes and paired confidence arithmetic; optimizer updates and every solver decision are not replayed.')
    dump(DATA/'verification.json',report);print('SAVED EVIDENCE VERIFIED',flush=True)


if __name__=='__main__':main()
