"""Prospective cohort integrity, whole-run scoring and all-actor gates."""
from collections import Counter
from types import SimpleNamespace

import numpy as np
import pytest

from integrations.unified_lans.simulation import move_npcs
from tools.ppo_benefit_v10.core import PARAMS
from tools.unified_control_v9.learning import setup as make_pipeline

from . import evaluate
from .learning import Env, HORIZON
from .safety import Controller as SafeController


def fixture(delay=0.):
    return dict(id=0, stage='evaluation_semantic_unit_test', scenario='following',
                speed=8., delay=delay, mirror=1, stiffness=1.15, lateral=.25,
                heading=-.01, phase=1.3, amplitude=.9, network='nominal',
                network_seed=9139, npc_x_shift=5., npc_speed_scale=1.)


class Zero:
    def predict(self, query, deterministic=True):
        assert deterministic and query.shape == (55,)
        return np.zeros(8, np.float32), None


def fake_records():
    # This independent test namespace is never either prospective namespace.
    cases = evaluate.draw_cases(np.random.default_rng(99107), 1, 'synthetic_unit_test')
    return [dict(case=case, mode=mode, seed=seed, ticks=120, expected_ticks=120,
                 rmse_m=.88 if mode == 'ppo' else 1., heading_rms=.01,
                 rate_rms=.02, progress_m=60., failed=False, collisions=0,
                 corridor_failures=0, selected_ticks=int(mode == 'ppo'))
            for case in cases for mode in evaluate.MODES for seed in evaluate.seeds_for(mode)]


def test_case_constructor_keeps_all_strata_mirrors_and_state_replicas():
    for draws, expected in ((1, 72), (2, 144)):
        cases = evaluate.draw_cases(np.random.default_rng(99108), draws, 'synthetic_unit_test')
        assert len(cases) == expected
        counts = Counter((c['scenario'], c['speed'], c['delay'], c['mirror']) for c in cases)
        assert len(counts) == 72 and set(counts.values()) == {draws}
        assert all(10 <= c['phase'] < 28 and .9 <= c['amplitude'] < 1.3 for c in cases)
        assert all(.75 <= c['stiffness'] < 1.25 and .15 <= c['lateral']*c['mirror'] < .45 for c in cases)
        assert len({c['network_seed'] for c in cases}) == expected


def test_unfrozen_endpoints_prevent_prospective_rng_and_output(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'DATA', tmp_path)
    def reject():
        raise AssertionError('endpoints not frozen')
    def forbidden(*args, **kwargs):
        raise RuntimeError('prospective RNG was opened too early')
    monkeypatch.setattr(evaluate, 'frozen_policies', reject)
    monkeypatch.setattr(evaluate, 'draw_cases', forbidden)
    with pytest.raises(AssertionError, match='endpoints not frozen'):
        evaluate.prepare('validation')
    assert not (tmp_path/'validation').exists()


def test_extra_supervised_control_is_required_and_no_overall_transfer_claim():
    records = fake_records()
    result = evaluate.assess(records, 99109)
    assert result['episodes'] == 864 and result['numerical_qualification_passed']
    assert result['requested_10_mean_passed'] and result['inferential_at_least_10_passed']
    assert not result['overall_qualified']
    assert not result['runtime_validated'] and not result['native_transfer_validated']
    for row in records:
        if row['mode'] == 'continued_bc':
            row['rmse_m'] = .8
    result = evaluate.assess(records, 99109)
    assert not result['numerical_qualification_passed']
    assert 'confidence_continued_bc' in result['reasons']


def test_one_actor_heading_failure_is_not_hidden_by_policy_average():
    records = fake_records()
    for row in records:
        if row['mode'] == 'ppo':
            row['heading_rms'] = .012 if row['seed'] == 43 else .009
    result = evaluate.assess(records, 99109)
    assert result['metrics']['ppo']['heading_rms'] < 1.1*result['metrics']['lqr']['heading_rms']
    assert 'actor_43_heading' in result['reasons']
    assert not result['numerical_qualification_passed']


def test_single_case_safety_and_progress_failures_are_retained():
    records = fake_records()
    failed = next(r for r in records if r['mode'] == 'ppo' and r['seed'] == 42)
    failed.update(failed=True, collisions=1, ticks=47, rmse_m=2.01, progress_m=59.3)
    result = evaluate.assess(records, 99109)
    assert result['episodes'] == 864 and result['failures']['ppo'] == 1
    assert result['actors']['42']['collisions'] == 1
    assert 'actor_42_safety' in result['reasons'] and 'actor_42_progress' in result['reasons']
    assert result['actors']['42']['minimum_progress_ratio_to_lqr'] == pytest.approx(59.3/60.)


def test_bootstrap_keeps_all_seed_mirror_pairs_in_each_of_36_strata():
    records = fake_records()
    references, candidates = [], []
    for index, stratum in enumerate(evaluate.STRATA):
        reference = 1.+index/10.
        ratio = .7 if index % 2 else 1.1
        references.append(reference)
        candidates.append(reference*ratio)
        for row in records:
            c = row['case']
            if (c['scenario'], c['speed'], c['delay']) == stratum:
                if row['mode'] == 'ppo':
                    # Mirror and policy offsets cancel only when all are kept.
                    row['rmse_m'] = reference*ratio + .01*c['mirror'] + .001*(row['seed']-43)
                else:
                    row['rmse_m'] = reference
    seed = 99110
    draws = np.random.default_rng(seed).integers(36, size=(5000, 36))
    a, b = np.asarray(references), np.asarray(candidates)
    expected = np.quantile(100*(1-b[draws].mean(axis=1)/a[draws].mean(axis=1)), [.025, .975])
    result = evaluate.assess(records, seed)
    comparison = result['comparisons']['adaptive']
    np.testing.assert_allclose(comparison['ci95_percent'], expected, atol=1e-12)
    assert comparison['gain_percent'] == pytest.approx(100*(1-b.mean()/a.mean()))
    assert comparison['clusters'] == 36 and comparison['conditional_on_three_trained_policies']
    # Mean >=10 is distinct from an inferential lower-bound >=10 claim.
    assert result['requested_10_mean_passed']
    assert not result['adaptive_ci_lower_at_least_10']


@pytest.mark.parametrize('delay', [0., .05, .1])
def test_zero_actor_evaluation_matches_training_task_on_every_physical_tick(delay):
    case = fixture(delay)
    record, rows = evaluate.run(case, 'ppo', 42, models={'ppo-42': Zero()})
    env = Env(controller_kwargs=evaluate.CONTROLLER_KWARGS)
    query, _ = env.reset(seed=3, options={'case': case})
    try:
        assert len(rows) == record['ticks'] == HORIZON
        for evaluated in rows:
            np.testing.assert_array_equal(evaluated['observation'], query)
            query, reward, done, truncated, trained = env.step(np.zeros(8))
            for key in ('state_before', 'state_after', 'shadow_before', 'shadow_after'):
                np.testing.assert_array_equal(evaluated[key], trained[key])
            for key in ('issued_steering', 'issued_accel', 'applied_steering', 'applied_accel',
                        'steering_rate', 'error', 'heading_error', 'score_error_sq', 'reward'):
                assert evaluated[key] == trained[key]
            assert evaluated['terminated'] == done and not truncated
        assert record['primary_reward'] == pytest.approx(sum(r['reward_parts']['rmse_reward'] for r in rows))
        assert record['rmse_m'] == pytest.approx(np.sqrt(sum(r['error']**2 for r in rows)/120))
    finally:
        env.close()


def test_lqr_reference_keeps_its_original_mode_and_no_grid():
    case = fixture(.1)
    record, rows = evaluate.run(case, 'lqr', 0)
    ref, clock, state, npcs, net = make_pipeline(
        case, 'lqr', SafeController, dict(PARAMS, adaptive=False, mpc=False), grid=False,
    )
    for tick, row in enumerate(rows):
        now = tick*.05
        clock.now = now
        net.emit(now, state, npcs, ref.inbox)
        decision = ref.decide(now)
        state = ref.apply(now, state, case['stiffness'])
        move_npcs(npcs, .05, ref.route, case['scenario'])
        assert row['issued_steering'] == decision['issued_steering']
        assert row['issued_accel'] == decision['issued_accel']
        np.testing.assert_array_equal(row['state_after'], state)
    assert record['selected_ticks'] == 0 and not record['failed']


def test_refiner_respects_first_admissible_scale_even_without_first_change():
    class Owner:
        projection_scales = (1., .5, .25)
        def score_candidate(self, ctx, profile, scale):
            # The first profile is nominally best but its first admitted scale
            # changes only a future command. finish must keep the owner there.
            if tuple(profile) == evaluate.REFINER_PROFILES[0]:
                return SimpleNamespace(admissible=True, cost=.5 if scale == 1. else .1,
                                       first=0. if scale == 1. else .01)
            return SimpleNamespace(admissible=True, cost=.8, first=.02)
    ctx = SimpleNamespace(eligible=True, reference_values=((1.,0.,0.,0.),)*3, reference_first=0.)
    action, report = evaluate.refiner(Owner(), ctx)
    assert tuple(action) == evaluate.REFINER_PROFILES[1]
    assert report['score_evaluations'] == 4 and report['selected_projection_scale'] == 1.


def test_refiner_outputs_are_rechecked_by_the_actual_owner():
    record, rows = evaluate.run(fixture(.05), 'refiner', 0)
    assert record['ticks'] == 120 and not record['failed']
    assert record['refiner_evaluations'] > 0
    for row in rows:
        if row['sequence_plan_selected']:
            assert row['refiner']['selected_profile'] is not None
            assert row['projection_scale'] == row['refiner']['selected_projection_scale']
            assert row['sequence_cost'] < row['anchor_reference_cost']-1e-8
            assert row['sequence_margin'] >= 0
            values = np.asarray(row['applied_score_values'])
            reference = np.asarray(row['context']['lqr_values'])
            assert np.all(values[:,0] < reference[:,0]-1e-9)
            assert np.all(values[:,2] <= 1.21*reference[:,2]+2e-6)
            assert np.all(values[:,3] <= 1.21*reference[:,3]+1e-5)
