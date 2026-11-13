"""Frozen completion selection/gates and durable orchestration, without missions."""
from copy import deepcopy

import numpy as np
import pytest

from . import complete, evaluate, verify_calibration


def test_timing_isolates_other_numerical_leaders_but_allows_its_own_auditor(monkeypatch):
    from pathlib import Path as RealPath
    from types import SimpleNamespace
    own=12340
    commands={
        own:['python','-m','tools.ppo_complete_v13.verify','--reuse'],
        own+1:['python','-m','tools.ppo_complete_v13.verify_evaluation','final'],
        own+2:['python','-m','unrelated.application'],
        own+3:['python','-m','tools.ppo_complete_v13.train','learn'],
        own+4:['python','-m','tools.ppo_complete_v13.complete','native'],
        own+5:['python','-m','tools.ppo_opportunity_v14.pilot'],
    }
    class Process:
        def __init__(self,pid):self.name=str(pid)
        def __truediv__(self,name):
            assert name=='cmdline'
            return SimpleNamespace(read_bytes=lambda:b'\0'.join(x.encode() for x in commands[int(self.name)]))
    tree=SimpleNamespace(iterdir=lambda:[Process(pid) for pid in commands])
    monkeypatch.setattr(complete,'Path',lambda value:tree if value=='/proc' else RealPath(value))
    monkeypatch.setattr(complete.os,'getpid',lambda:own)
    assert complete.active_training()==[own+1,own+3,own+4,own+5]


def all_cases(draws):
    return evaluate.draw_cases(np.random.default_rng(99120), draws, 'synthetic_completion_unit_test')


def protocol(kind):
    cases = complete.select_cases(all_cases(1 if kind=='runtime' else 2), kind)
    return dict(kind=kind,cases=cases,bootstrap_seed=complete.BOOTSTRAP_SEEDS[kind],
        expected_owner_slots=len(cases)*5*120,
        expected_native_physics_steps=len(cases)*5*6000 if kind=='native' else 0,
        role='synthetic_test_only',scope='Synthetic test fixtures, no research outcomes')


def record(case,mode,seed,kind):
    return dict(case=case,mode=mode,seed=seed,ticks=120,expected_ticks=120,
        rmse_m=.88 if mode=='ppo' else 1.,heading_rms=.01,rate_rms=.02,
        commanded_rate_rms=.001,progress_m=60.,failed=False,collisions=0,
        corridor_failures=0,owner_response_misses=0,scheduled_response_misses=0,
        policy_worker_failures=0,policy_reply_count=120 if mode=='ppo' else 0,
        selected_ticks=1 if mode=='ppo' else 0,owner_max_ms=2.,
        raw_physics_steps=6000 if kind=='native' else 0,
        world_sha256='same-world-for-case-'+str(case['id']),
        scene_calibration=dict(verified=True,scene_state_sha256='same-scene-for-case-'+str(case['id'])),
        initial_state_fidelity=dict(all_initial_speeds_within_01_m_s=True))


def records_for(p):
    return [record(c,m,s,p['kind']) for c in p['cases'] for m,s in complete.ROLES]


def test_selection_is_fixed_before_any_outcomes_and_covers_declared_domain():
    runtime_cases = complete.select_cases(all_cases(1),'runtime')
    assert len(runtime_cases)==36 and [c['id'] for c in runtime_cases]==list(range(0,72,2))
    assert {c['mirror'] for c in runtime_cases}=={-1}
    native_cases = complete.select_cases(all_cases(2),'native')
    assert len(native_cases)==24 and all(c['replica']==0 for c in native_cases)
    assert len({(c['scenario'],c['speed'],c['mirror']) for c in native_cases})==24
    assert len({(c['scenario'],c['speed'],c['delay']) for c in native_cases})==12
    assert {c['delay'] for c in native_cases}=={0.,.05,.1}


@pytest.mark.parametrize('kind,episodes,slots,physics',[('runtime',180,21600,0),('native',120,14400,720000)])
def test_full_measured_stage_still_cannot_claim_framework_qualification(kind,episodes,slots,physics):
    p=protocol(kind)
    result=complete.assess_stage(records_for(p),p)
    assert result['episodes']==episodes and result['observed_owner_slots']==slots
    assert result['observed_native_physics_steps']==physics
    assert result['mean_target_qualified'] and result['inferential_target_qualified']
    assert not result['overall_qualified']


def test_realized_native_rate_cannot_be_replaced_by_good_commanded_rate():
    p=protocol('native');records=records_for(p)
    for r in records:
        if r['mode']=='ppo' and r['seed']==43:r['rate_rms']=.03
    result=complete.assess_stage(records,p)
    assert 'actor_43_rate' in result['reasons']
    assert result['actors']['43']['rate_ratio_to_lqr']==pytest.approx(1.5)
    assert not result['mean_target_qualified']


def test_one_scheduled_deadline_miss_disqualifies_and_remains_counted():
    p=protocol('runtime');records=records_for(p)
    records[0]['scheduled_response_misses']=1
    result=complete.assess_stage(records,p)
    assert result['scheduled_response_misses']==1 and not result['timing_passed']
    assert 'actual_owner_or_scheduled_timing' in result['reasons']
    assert not result['mean_target_qualified']


def test_initial_native_speed_mismatch_has_a_separate_frozen_gate():
    p=protocol('native');records=records_for(p)
    records[0]['initial_state_fidelity']['all_initial_speeds_within_01_m_s']=False
    result=complete.assess_stage(records,p)
    assert not result['initial_speed_fidelity_passed']
    assert 'native_initial_speed_fidelity' in result['reasons']


def test_paired_native_bootstrap_keeps_both_mirrors_and_all_three_policies():
    p=protocol('native');records=records_for(p);groups=sorted({(c['scenario'],c['speed'],c['delay']) for c in p['cases']})
    a=[];b=[]
    for index,key in enumerate(groups):
        ref=1.+index/8.;candidate=ref*(.7 if index%2 else 1.05);a.append(ref);b.append(candidate)
        for r in records:
            c=r['case']
            if (c['scenario'],c['speed'],c['delay'])==key:
                r['rmse_m']=candidate+.01*c['mirror']+.001*(r['seed']-43) if r['mode']=='ppo' else ref
    draw=np.random.default_rng(p['bootstrap_seed']).integers(12,size=(5000,12))
    expected=np.quantile(100*(1-np.asarray(b)[draw].mean(axis=1)/np.asarray(a)[draw].mean(axis=1)),[.025,.975])
    result=complete.assess_stage(records,p)
    np.testing.assert_allclose(result['comparisons']['adaptive']['ci95_percent'],expected,atol=1e-12)
    assert result['comparisons']['adaptive']['clusters']==12


def test_missing_role_or_execution_error_cannot_get_partial_pass():
    p=protocol('runtime');records=records_for(p)
    result=complete.assess_stage(records[:-1],p)
    assert not result['complete'] and len(result['missing_roles'])==1
    assert not result['mean_target_qualified']
    result=complete.assess_stage(records,p,[dict(error='synthetic execution error')])
    assert not result['complete'] and result['execution_errors']==1


def mock_inputs():
    return dict(policies={f'ppo-{s}':dict(path=f'fake-models/seed-{s}/policy.zip',sha256='synthetic',
                  manifest_path=f'fake-models/seed-{s}/manifest.json',manifest_sha256='synthetic') for s in complete.SEEDS},
        input_hashes={},python_stages={stage:dict(cases=all_cases(draws),assessment=dict(
            numerical_qualification_passed=False,inferential_at_least_10_passed=False))
            for stage,draws in (('validation',1),('final',2))})


def mock_common(monkeypatch,tmp_path):
    monkeypatch.setattr(complete,'DATA',tmp_path)
    monkeypatch.setattr(complete,'frozen_inputs',mock_inputs)
    monkeypatch.setattr(complete,'source_snapshot',lambda _: {})
    monkeypatch.setattr(complete,'check_freeze',lambda *_:None)


def test_runtime_runner_is_sequential_retains_python_failure_and_refuses_rerun(monkeypatch,tmp_path):
    mock_common(monkeypatch,tmp_path);calls=[]
    def fake_profile(cases,output,**kwargs):
        output.mkdir(exist_ok=False);calls.append((cases,output,kwargs))
    monkeypatch.setattr(complete.runtime,'profile',fake_profile)
    monkeypatch.setattr(complete,'_runtime_records',lambda folder,cases,mode,seed:[record(c,mode,seed,'runtime') for c in cases])
    result=complete.run('runtime')
    assert len(calls)==5 and [c[2]['mode'] for c in calls]==['lqr','adaptive','ppo','ppo','ppo']
    assert all(c[2]['steps']==120 and len(c[0])==36 for c in calls)
    assert all(c[2]['role']=='frozen_policy_transfer_diagnostic_after_python_gate_failure' for c in calls)
    assert result['episodes']==180
    with pytest.raises(AssertionError,match='refusing to overwrite'):
        complete.run('runtime')
    assert len(calls)==5


def test_native_runner_reuses_one_policy_free_scene_per_case_all_actors(monkeypatch,tmp_path):
    mock_common(monkeypatch,tmp_path);calls=[]
    calibration=tmp_path/'native-actuator-calibration-v3';calibration.mkdir()
    for name in ('protocol.json','summary.json','verification.json'):(calibration/name).write_text('{}')
    monkeypatch.setattr(verify_calibration,'verify',lambda _:dict(verified=True,all_initial_speeds_settled=True))
    monkeypatch.setattr(complete,'ROOT',tmp_path)
    def fake_episode(output,case,mode,policy,role,*,scene_calibration):
        output.mkdir(exist_ok=False);scene_calibration.mkdir(parents=True,exist_ok=True)
        calls.append((case['id'],mode,policy,scene_calibration))
    monkeypatch.setattr(complete.native,'episode',fake_episode)
    monkeypatch.setattr(complete,'_native_record',lambda folder,case,mode,seed:record(case,mode,seed,'native'))
    result=complete.run('native')
    assert len(calls)==120 and result['episodes']==120
    for case_id in complete.NATIVE_IDS:
        cc=[c for c in calls if c[0]==case_id]
        assert len(cc)==5 and len({c[3] for c in cc})==1
        assert [c[1] for c in cc]==['lqr','adaptive','ppo','ppo','ppo']
    assert len({str(c[2]) for c in calls if c[1]=='ppo'})==3


def test_failed_runtime_unit_is_journaled_and_other_roles_still_run(monkeypatch,tmp_path):
    mock_common(monkeypatch,tmp_path);calls=[]
    def fake_profile(cases,output,**kwargs):
        calls.append(kwargs['mode'])
        output.mkdir(exist_ok=False)
        if kwargs['mode']=='adaptive':raise RuntimeError('synthetic host failure')
    monkeypatch.setattr(complete.runtime,'profile',fake_profile)
    monkeypatch.setattr(complete,'_runtime_records',lambda folder,cases,mode,seed:[record(c,mode,seed,'runtime') for c in cases])
    with pytest.raises(RuntimeError,match='1 retained runtime execution errors'):
        complete.run('runtime')
    assert len(calls)==5
    summary=complete.read(tmp_path/'completion/runtime/summary.json')
    assert len(summary['records'])==144 and len(summary['execution_errors'])==1
    assert not summary['assessment']['complete']
    journal=(tmp_path/'completion/runtime/journal.jsonl').read_text()
    assert 'synthetic host failure' in journal and '"verified": false' in journal


def test_training_detection_blocks_before_opening_any_endpoint_or_case(monkeypatch):
    monkeypatch.setattr(complete,'active_training',lambda:[123])
    def forbidden():raise RuntimeError('endpoint/case opened before training stopped')
    monkeypatch.setattr(evaluate,'frozen_policies',forbidden)
    with pytest.raises(AssertionError,match='cannot overlap V13 learning'):
        complete.frozen_inputs()
