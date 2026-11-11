"""Raw physical replay, causal features, strong-reference reward and plan audit."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,math,multiprocessing as mp
import numpy as np
from integrations.unified_lans.physics import Command,Config,constrain,advance,errors
from integrations.unified_lans.traffic import Packet,velocity
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.inference import sha
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v9.learning import setup
from tools.unified_control_v9.verify import equal
from tools.ppo_benefit_v10.core import PARAMS,observation as scalar_features
from .control import Controller,PlanProposal
from .learning import ROOT,DATA,features,shaping,reconstruct
from .probe import dump
from .verify import plan_python


def sources(folder):
    p=json.loads((folder/'protocol.json').read_text())
    for name,digest in p['source_hashes'].items():
        assert sha(folder/'source'/name)==digest,('Snapshot',name)
        # Only mathematical replay dependencies must remain active at the same
        # path. Independent driver/audit additions retain their saved snapshots.
        if name.startswith('tools/ppo_plan_v11/') and Path(name).name not in ('control.py','learning.py'):continue
        assert sha(ROOT/name)==digest,('Replay dependency',name)
    return p


def ingest(c,now,state,npcs):
    sequence=round(now/.05)
    assert c.inbox.ingest(Packet('ego',sequence,now,tuple(state)),now)
    for name,other in npcs.items():assert c.inbox.ingest(Packet(name,sequence,now,tuple(other)),now)


def rollout(z,first,plan,accel,previous,c,model,vehicles):
    state=z.copy();value=0.;margin=1e9;heading=0.;rate_energy=0.
    for i in range(40):
        base=c.baseline_fn(state,c.route);u=first if i==0 else base
        if i>0 and plan is not None:u=min(base+.08,max(base-.08,plan[i]))
        if i>0:u=min(previous+.03,max(previous-.03,u))
        u=min(.5,max(-.5,u));state=advance(state,Command(u,accel),.05,model)
        error,_=errors(state,c.route);ey,ep=error[0],error[2];rate=(u-previous)/.05
        value+=.05*(8*ey**2+2*ep**2+.03*u*u+.02*rate*rate);heading+=.05*ep**2;rate_energy+=.05*rate*rate
        margin=min(margin,1.75-abs(ey));t=(i+1)*.05
        for _,other,uncertainty in vehicles:
            future=other[:2]+velocity(other)*t
            margin=min(margin,float(np.linalg.norm(future-state[:2]))-4.6-.5-uncertainty-.6*t)
        previous=u
    return np.array([value,margin,heading,rate_energy])


def admitted(c,row,now,prior,previous):
    assert prior is not None and row['source']=='ppo_plan' and c.fresh_plan(now)
    assert row['sequence_plan_selected'] and not row['ego_backup'] and row['risk']!='DANGER'
    assert row['sequence_shift']==0 and 0<=row['sequence_age']<.15 and 0<=row['sequence_wall_age']<.15
    equal(row['sequence_knots'],list(prior.knots))
    z=c.forecast(now);ref=Base.decide(c,now)
    assert ref['eligible'][ref['source']]
    equal(row['sequence_reference_cost'],ref['costs'][ref['source']]);equal(row['issued_accel'],ref['issued_accel'])
    c.pending.pop();c.issued=previous
    old=c.supervisor.state;risk=c.supervisor.assess(z,c.inbox,c.expected,now,now+c.delay);c.supervisor.state=old
    plan=plan_python(z,prior.knots,0,row['issued_accel'],previous.steering,c.route,c.feedback_stiffness,c.stiffness_estimate)
    equal(plan[0],row['issued_steering'])
    baseline=constrain(Command(c.baseline_fn(z,c.route),row['issued_accel']),previous,c.cfg)
    center=c.stiffness_estimate;width=c.stiffness_uncertainty;models=[max(.7,center-width),center,min(1.3,center+width)]
    candidate=np.asarray([rollout(z,plan[0],plan,row['issued_accel'],previous.steering,c,m,risk.vehicles) for m in models])
    reference=np.asarray([rollout(z,baseline.steering,None,row['issued_accel'],previous.steering,c,m,risk.vehicles) for m in models])
    assert np.all(candidate[:,0]<reference[:,0]-1e-9+1e-12)
    assert np.all(candidate[:,2]<=1.21*reference[:,2]+2e-6+1e-12)
    assert np.all(candidate[:,3]<=1.21*reference[:,3]+1e-5+1e-12)
    equal(row['sequence_cost'],float(candidate[:,0].mean()));equal(row['sequence_margin'],float(candidate[:,1].min()))
    assert candidate[:,1].min()>=-1e-12 and row['sequence_cost']<row['sequence_reference_cost']-1e-8


def training_worker(seed):
    folder=DATA/f'policies/seed-{seed}';p=sources(folder);m=json.loads((folder/'manifest.json').read_text())
    assert m['steps']==32768 and sha(folder/'policy.zip')==m['policy_sha256'] and sha(folder/'bc-policy.zip')==m['bc_policy_sha256']
    path=folder/'training.jsonl';assert sha(path)==m['trace_sha256']
    episode=-1;count=0;selected=0;failures=0;prior=None
    for line in path.open():
        row=json.loads(line);case=row['case'];now=row['time_s'];tick=row['tick']
        if row['episode_id']!=episode:
            assert tick==0;episode=row['episode_id']
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
        # Re-run the complete strong analytical shadow rather than inferring its
        # absent issued-command log from its applied commands.
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
    assert count==32768
    return dict(seed=seed,steps=count,independently_audited_plans=selected,failures=failures,shadow_controller_replayed=True)


def evaluate_record(meta):
    from .evaluate import OUT
    case=meta['case'];mode=meta['mode'];seed=meta['seed'];path=OUT/f'{case["id"]:03d}-{mode}-{seed}.jsonl'
    assert sha(path)==meta['raw_sha256'] and meta['protocol_sha256']==sha(OUT/'protocol.json')
    equal(json.loads(path.with_suffix('.json').read_text()),meta)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    cls=Controller if mode not in ('lqr','adaptive','scalar') else Base
    c,clock,state,npcs,_=setup(case,'lqr' if mode=='lqr' else ('hybrid' if mode=='scalar' else 'deterministic'),cls,
        dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
    prior=None;previous=Command();selected=0
    for i,row in enumerate(rows):
        now=i*.05;clock.now=now;assert row['tick']==i and row['time_s']==now
        np.testing.assert_allclose(row['state_before'],state,rtol=0,atol=1e-12);ingest(c,now,state,npcs);c.update_model()
        if prior is not None:
            assert (c.accept(prior,now) if mode=='scalar' else c.accept_plan(prior,now))
        issued_before=c.issued
        if row.get('sequence_plan_selected'):admitted(c,row,now,prior,issued_before);selected+=1
        actual=Command(row['issued_steering'],row['issued_accel']);assert abs(actual.steering-issued_before.steering)<=.03+1e-12
        if mode in ('lqr','adaptive','scalar'):
            reference=c.decide(now);equal(reference['issued_steering'],actual.steering);equal(reference['issued_accel'],actual.accel)
        else:c.pending.append((now+case['delay'],actual));c.issued=actual
        state=c.apply(now,state,case['stiffness']);np.testing.assert_allclose(row['state_after'],state,rtol=0,atol=1e-12)
        assert c.applied==Command(row['applied_steering'],row['applied_accel'])
        equal(row['steering_rate'],(c.applied.steering-previous.steering)/.05)
        move_npcs(npcs,.05,c.route,case['scenario'])
        for name,other in npcs.items():np.testing.assert_allclose(row['npc_truth'][name],other,rtol=0,atol=1e-12)
        truth=truth_metrics(state,npcs,c.route,c.cfg)
        for name,value in truth.items():equal(row[name],value)
        if row['label'] is not None:
            label=row['label'];assert np.isfinite(label).all()
            if mode=='scalar':
                from integrations.unified_lans.controller import Proposal
                prior=Proposal(i+1,now,now,float(label[0])*.08,now)
            else:prior=PlanProposal(i+1,now,now,now,tuple(label))
        previous=c.applied
    n=len(rows);assert n==meta['ticks'] and meta['expected_ticks']==120
    values=dict(failed=n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
        heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
        rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(state[0]),
        collisions=sum(r['collision'] for r in rows),selected_ticks=sum(r['source'] in ('ppo','ppo_plan') for r in rows))
    for name,value in values.items():equal(meta[name],value)
    return dict(ticks=n,independently_audited_plans=selected)


def main():
    import torch
    torch.set_num_threads(1)
    dataset=DATA/'dataset';p=sources(dataset);m=json.loads((dataset/'manifest.json').read_text())
    assert sha(dataset/'dataset.npz')==m['dataset_sha256'];data=np.load(dataset/'dataset.npz');offset=0
    for case in json.loads((DATA/'probe/protocol.json').read_text())['cases']:
        path=DATA/f'probe/{case["id"]:03d}-sequence_teacher.jsonl';assert sha(path)==p['inputs'][str(path.relative_to(ROOT))]
        rows=[json.loads(line) for line in path.read_text().splitlines()];values=reconstruct(case,rows)
        np.testing.assert_array_equal(data['observations'][offset:offset+len(rows)],values)
        np.testing.assert_array_equal(data['actions'][offset:offset+len(rows)],np.asarray([r['label'] for r in rows],np.float32));offset+=len(rows)
    assert offset==m['samples']==7680
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        training=[f.result() for f in as_completed([pool.submit(training_worker,s) for s in (42,43,44)])]
    print('VERIFIED ALL 98304 PPO AND SHADOW TRANSITIONS',flush=True)
    out=DATA/'evaluation';p=sources(out);records=json.loads((out/'summary.json').read_text());assert len(records)==864
    for record in p['policies'].values():assert sha(ROOT/record['path'])==record['sha256']
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        audited=[f.result() for f in as_completed([pool.submit(evaluate_record,r) for r in records])]
    # Paired arithmetic is independently rebuilt from the raw-verified per-case scores.
    assessment=json.loads((out/'assessment.json').read_text());lookup={(r['case']['id'],r['mode'],r['seed']):r for r in records}
    assert len(lookup)==864
    for mode in ('lqr','adaptive','teacher','scalar','bc'):
        groups={}
        for case in p['cases']:
            i=case['id'];a=[lookup[(i,mode,s)]['rmse_m'] for s in ((42,43,44) if mode in ('scalar','bc') else [0])]
            b=[lookup[(i,'ppo',s)]['rmse_m'] for s in (42,43,44)]
            groups.setdefault((case['scenario'],case['speed'],case['delay']),[]).append([np.mean(a),np.mean(b)])
        pairs=np.asarray([np.mean(v,axis=0) for v in groups.values()]);mean=pairs.mean(axis=0)
        draw=np.random.default_rng(2134114).integers(36,size=(5000,36));samples=pairs[draw].mean(axis=1)
        equal(assessment['comparisons'][mode]['gain_percent'],100*(1-mean[1]/mean[0]))
        equal(assessment['comparisons'][mode]['ci95_percent'],np.quantile(100*(1-samples[:,1]/samples[:,0]),[.025,.975]).tolist())
    report=dict(passed=True,teacher_samples=7680,training=sorted(training,key=lambda r:r['seed']),evaluation_episodes=864,
        evaluation_ticks=sum(r['ticks'] for r in audited),independently_audited_eval_plans=sum(r['independently_audited_plans'] for r in audited),
        source_sha256=sha(__file__),assessment_sha256=sha(out/'assessment.json'),
        limitation='Actor optimizer trajectories not rerun; actual physics, complete analytical reward shadows and all admitted sequence guards are replayed. Shaping is recomputed from frozen causal model code.')
    dump(DATA/'verification.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
