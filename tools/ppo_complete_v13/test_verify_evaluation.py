"""Corruption tests for independent V13 evaluation and complete-stage audits."""
from copy import deepcopy
import json

import numpy as np
import pytest

from . import evaluate, verify, verify_evaluation
from . import verify_training
from .headroom import jsonable


class Zero:
    def predict(self, observation, deterministic=True):
        assert deterministic and observation.shape == (55,)
        return np.zeros(8, np.float32), None


def fixture(delay=0., failure=False):
    return dict(id=0, stage='independent_evaluation_audit_unit_only',
        scenario='following', speed=8., delay=delay, mirror=-1,
        stiffness=.85, lateral=-.25, heading=.01, phase=12., amplitude=1.1,
        network='nominal', network_seed=99130,
        npc_x_shift=-30. if failure else 0., npc_speed_scale=1.)


@pytest.fixture(scope='module')
def full_episode():
    meta, rows = evaluate.run(fixture(.1), 'ppo', 42, {'ppo-42': Zero()})
    return jsonable(meta), jsonable(rows)


@pytest.mark.parametrize('delay', [0., .05, .1])
def test_source_controller_and_independent_physics_replay_complete_episode(tmp_path, monkeypatch, delay):
    meta, rows = evaluate.run(fixture(delay), 'ppo', 42, {'ppo-42': Zero()})
    meta, rows = jsonable(meta), jsonable(rows)
    path = tmp_path/'000-ppo-42.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (tmp_path/'protocol.json').write_text('{"synthetic_unit_only":true}\n')
    meta.update(raw_sha256=verify_evaluation.digest(path),
        protocol_sha256=verify_evaluation.digest(tmp_path/'protocol.json'))
    path.with_suffix('.json').write_text(json.dumps(meta))
    monkeypatch.setattr(verify_evaluation, 'OUTPUT', tmp_path)
    monkeypatch.setattr(verify_evaluation, 'MODELS', {'ppo-42': Zero()})
    result = verify_evaluation.episode(meta)
    assert result['ticks'] == 120 and not result['failed']


@pytest.mark.parametrize('tamper', ['plant', 'shadow', 'fifo', 'reward', 'terminal', 'summary', 'dropped_tick'])
def test_independent_episode_audit_rejects_material_tampering(full_episode, tamper):
    meta, rows = deepcopy(full_episode)
    if tamper == 'plant':
        rows[20]['state_after'][1] += .01
    elif tamper == 'shadow':
        rows[20]['shadow_after'][1] += .01
    elif tamper == 'fifo':
        rows[0]['applied_steering'] += .01
    elif tamper == 'reward':
        rows[-1]['reward_parts']['rmse_reward'] += 1.
    elif tamper == 'terminal':
        rows[-1]['truncated'] = True
    elif tamper == 'summary':
        meta['rmse_m'] *= .7
    else:
        rows.pop(20)
    with pytest.raises(AssertionError):
        verify_evaluation.physical_record(meta, rows)


def test_failed_episode_audit_keeps_all119_missing_tick_penalties():
    meta, rows = evaluate.run(fixture(failure=True), 'adaptive', 0)
    meta, rows = jsonable(meta), jsonable(rows)
    assert len(rows) == 1 and rows[0]['collision']
    result = verify_evaluation.physical_record(meta, rows)
    expected = np.sqrt((rows[0]['error']**2+119*6.25)/120)
    assert result['failed'] and result['rmse_m'] == pytest.approx(expected)
    rows[0]['score_error_sq'] -= 6.25
    with pytest.raises(AssertionError):
        verify_evaluation.physical_record(meta, rows)


def synthetic_statistics():
    # Never construct either registered prospective RNG namespace.
    cases = evaluate.draw_cases(np.random.default_rng(99131), 1, 'independent_audit_unit_only')
    records = [dict(case=c, mode=m, seed=s, ticks=120, expected_ticks=120,
        rmse_m=.88 if m == 'ppo' else 1., heading_rms=.01, rate_rms=.02,
        progress_m=60., failed=False, collisions=0, corridor_failures=0,
        selected_ticks=int(m == 'ppo'))
        for c in cases for m in evaluate.MODES for s in evaluate.seeds_for(m)]
    protocol = dict(cases=cases, bootstrap_seed=99132)
    return records, protocol


def test_independent_statistics_checks_bootstrap_and_single_actor_failure():
    records, protocol = synthetic_statistics()
    for r in records:
        if r['mode'] == 'ppo':
            r['heading_rms'] = .012 if r['seed'] == 43 else .009
    assessment = evaluate.assess(records, protocol['bootstrap_seed'])
    proof = verify_evaluation.statistics(records, assessment, protocol)
    assert proof['all_actors_and_failures_retained']
    assert 'actor_43_heading' in proof['reasons']
    assert assessment['metrics']['ppo']['heading_rms'] < 1.1*assessment['metrics']['lqr']['heading_rms']
    assessment['comparisons']['adaptive']['ci95_percent'][0] += .1
    with pytest.raises(AssertionError):
        verify_evaluation.statistics(records, assessment, protocol)


@pytest.mark.parametrize('error,status', [(FileNotFoundError('missing'), 'MISSING'),
    (verify.IncompleteEvidence('partial'), 'INCOMPLETE'), (AssertionError('corrupt'), 'FAILED')])
def test_incomplete_invalid_stages_never_receive_verified_status(error, status):
    def operation():
        raise error
    assert verify.audit_stage('native', operation)['status'] == status


def test_cache_dependencies_pin_native_world_and_scene_while_excluding_generated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, 'ROOT', tmp_path)
    unit = tmp_path/'unit'
    for name in ('protocol.json', 'summary.json', 'case.json', 'scene-state.json',
            'project/worlds/episode.wbt', 'project/protos/Car.proto', 'source/geometry.py'):
        path = unit/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('original-'+name)
    cache = unit/'source/__pycache__/geometry.pyc'
    cache.parent.mkdir()
    cache.write_bytes(b'generated-not-evidence')
    inputs = verify.pinned_inputs(verify.evidence_dependencies(unit))
    assert len(inputs) == 7 and not any('__pycache__' in p for p in inputs)
    world = unit/'project/worlds/episode.wbt'
    world.write_text('changed physical world')
    with pytest.raises(AssertionError, match='Evidence changed'):
        verify.check_inputs(inputs)


def test_training_seed_proof_promotes_raw_input_pins_into_parent_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_training, 'ROOT', tmp_path)
    raw = tmp_path/'training.jsonl'
    raw.write_text('all raw training rows preserved\n')
    proof = tmp_path/'seed-proof.json'
    proof.write_text(json.dumps(dict(passed=True, input_hashes={'training.jsonl': verify_training.digest(raw)})))
    inputs = verify_training.proof_inputs(proof)
    assert set(inputs) == {'training.jsonl', 'seed-proof.json'}
    raw.write_text('changed after the completed seed audit\n')
    with pytest.raises(AssertionError, match='Training proof input changed'):
        verify_training.proof_inputs(proof)
