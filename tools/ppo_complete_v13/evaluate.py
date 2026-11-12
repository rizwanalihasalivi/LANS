"""Frozen V13 endpoints on prospective, matched complete-episode cohorts.

Importing this module never creates cases or opens either prospective RNG
namespace. ``prepare`` verifies every declared endpoint/control first. The
synthetic-clock comparisons here do not constitute a wall-clock/runtime test.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import math
import multiprocessing as mp
import shutil

import numpy as np

from integrations.unified_lans.inference import sha
from integrations.unified_lans.simulation import move_npcs, truth_metrics
from tools.ppo_benefit_v10.core import PARAMS
from tools.unified_control_v9.learning import setup

from .headroom import jsonable, write
from .learning import (
    ROOT, DATA, CONTRACT, HORIZON, RunningStats, controller_class, observe,
    rmse_reward, terminal_constraints,
)
from .plans import CorrectionProposal
from .safety import Controller as SafeController
from .train import CONTROLLER_KWARGS, SEEDS, STEPS, snapshot as training_snapshot

MODES = ('lqr', 'adaptive', 'bc', 'continued_bc', 'ppo', 'refiner')
LEARNED = ('bc', 'continued_bc', 'ppo')
COHORTS = {
    'validation': dict(case_seed=2134151, draws=1, bootstrap_seed=2134153),
    'final': dict(case_seed=2134152, draws=2, bootstrap_seed=2134154),
}
STRATA = tuple((scenario, speed, delay)
               for scenario in ('following', 'merge', 'crossing', 'curved')
               for speed in (8., 12., 16.) for delay in (0., .05, .1))
REFINER_PROFILES = tuple(tuple(float(x) for x in sign * .125 * profile)
                        for profile in (np.ones(8), np.exp(-np.linspace(0., 3.5, 8)))
                        for sign in (-1., 1.))
MODELS = {}
OUTPUT = None


def seeds_for(mode):
    if mode not in MODES:
        raise ValueError(f'unknown evaluation role: {mode}')
    return SEEDS if mode in LEARNED else (0,)


def draw_cases(rng, draws, stage):
    """Pure factorial constructor; tests use independent synthetic RNGs only."""
    if draws not in (1, 2):
        raise ValueError('the registered cohort has one or two draws per cell')
    result = []
    for scenario, speed, delay in STRATA:
        for mirror in (-1, 1):
            for replica in range(draws):
                result.append(dict(
                    id=len(result), stage=stage, scenario=scenario, speed=speed,
                    delay=delay, mirror=mirror, replica=replica,
                    stiffness=float(rng.uniform(.75, 1.25)),
                    lateral=float(rng.uniform(.15, .45)) * mirror,
                    heading=float(rng.uniform(-.02, .02)),
                    phase=float(rng.uniform(10., 28.)),
                    amplitude=float(rng.uniform(.9, 1.3)),
                    npc_x_shift=float(rng.uniform(-5., 5.)),
                    npc_speed_scale=float(rng.uniform(.75, 1.25)),
                    network='nominal',
                    network_seed=int(rng.integers(1_200_000_000, 1_900_000_000)),
                ))
    return result


def _check_current_sources(hashes):
    for name, digest in hashes.items():
        assert sha(ROOT / name) == digest, ('source changed after freeze', name)


def frozen_policies():
    """Check all three actors and matched controls before drawing any cases."""
    declaration = DATA / 'policies/declaration.json'
    declared = json.loads(declaration.read_text())
    assert declared['seeds'] == list(SEEDS) and declared['steps_per_seed'] == STEPS
    assert declared['protocol_sha256'] == sha(Path(__file__).with_name('TRAINING_PROTOCOL.md'))
    assert declared['source_sha256'] == sha(Path(__file__).with_name('train.py'))
    assert declared['fresh_evaluation_not_opened'] is True
    summaries = {
        'ppo': json.loads((DATA / 'policies/summary.json').read_text()),
        'continued_bc': json.loads((DATA / 'continued-bc/summary.json').read_text()),
    }
    for records in summaries.values():
        assert len(records) == 3 and {r['seed'] for r in records} == set(SEEDS)
    result = {}
    for seed in SEEDS:
        folder = DATA / f'policies/seed-{seed}'
        metadata = json.loads((folder / 'manifest.json').read_text())
        protocol = json.loads((folder / 'protocol.json').read_text())
        assert metadata == next(r for r in summaries['ppo'] if r['seed'] == seed)
        assert metadata['steps'] == STEPS and metadata['actor_steps'] > 0
        assert protocol['no_checkpoint_selection'] is True
        assert protocol['dataset_sha256'] == sha(DATA / 'dataset/dataset.npz')
        _check_current_sources(protocol['source_hashes'])
        continued_folder = DATA / f'continued-bc/seed-{seed}'
        continued = json.loads((continued_folder / 'manifest.json').read_text())
        assert continued == next(r for r in summaries['continued_bc'] if r['seed'] == seed)
        assert continued['steps'] == continued['actor_ppo_steps'] == 0
        assert continued['supervised_optimizer_steps'] == metadata['actor_steps']
        assert continued['source_bc_sha256'] == metadata['bc_policy_sha256']
        _check_current_sources(continued['source_hashes'])
        for mode, record, path, digest_key in (
            ('ppo', metadata, folder / 'policy.zip', 'policy_sha256'),
            ('bc', metadata, folder / 'bc-policy.zip', 'bc_policy_sha256'),
            ('continued_bc', continued, continued_folder / 'policy.zip', 'policy_sha256'),
        ):
            assert record['contract'] == CONTRACT
            assert record['observation_dim'] == 55 and record['action_dim'] == 8
            assert record['learner_class'] == 'IndependentPPO'
            assert record['controller_kwargs'] == CONTROLLER_KWARGS
            assert sha(path) == record[digest_key]
            result[f'{mode}-{seed}'] = dict(
                path=str(path.relative_to(ROOT)), sha256=record[digest_key],
                manifest_path=str((path.parent / 'manifest.json').relative_to(ROOT)),
                manifest_sha256=sha(path.parent / 'manifest.json'),
            )
    return result


def snapshot(out):
    hashes = training_snapshot(out)
    path = Path(__file__)
    name = str(path.relative_to(ROOT))
    hashes[name] = sha(path)
    target = out / 'source' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    return hashes


def prepare(stage):
    if stage not in COHORTS:
        raise ValueError('choose the registered validation or final cohort')
    out = DATA / stage
    assert not out.exists(), ('refusing to overwrite opened outcomes', out)
    policies = frozen_policies()
    validation = None
    if stage == 'final':
        prior = DATA / 'validation'
        protocol = json.loads((prior / 'protocol.json').read_text())
        assert protocol['policies'] == policies
        _check_current_sources(protocol['source_hashes'])
        records = json.loads((prior / 'summary.json').read_text())
        assert len(records) == 864
        assert json.loads((prior / 'assessment.json').read_text())['episodes'] == 864
        validation = dict(summary_sha256=sha(prior / 'summary.json'),
                          assessment_sha256=sha(prior / 'assessment.json'),
                          protocol_sha256=sha(prior / 'protocol.json'))
    # No prospective RNG is constructed before the endpoint/control checks.
    configuration = COHORTS[stage]
    cases = draw_cases(np.random.default_rng(configuration['case_seed']),
                       configuration['draws'], f'v13_prospective_{stage}')
    out.mkdir(parents=True, exist_ok=False)
    protocol = dict(
        stage=stage, **configuration, cases=cases, modes=MODES, seeds=SEEDS,
        episodes=12 * len(cases), policies=policies, source_hashes=snapshot(out),
        controller_kwargs=CONTROLLER_KWARGS, contract=CONTRACT,
        refiner_profiles=REFINER_PROFILES, bootstrap_draws=5000,
        target_increment_percent=10., validation_input=validation,
        no_model_or_case_selection=True, no_validation_tuning=True,
        score_horizon_ticks=120, unrun_tick_error_sq=6.25,
        runtime_test=False, native_transfer_test=False,
        policy_summary_sha256=sha(DATA / 'policies/summary.json'),
        continued_bc_summary_sha256=sha(DATA / 'continued-bc/summary.json'),
    )
    write(out / 'protocol.json', protocol)
    return protocol


def verify_protocol(out):
    protocol = json.loads((out / 'protocol.json').read_text())
    assert protocol['stage'] in COHORTS and protocol['policies'] == frozen_policies()
    assert protocol['controller_kwargs'] == CONTROLLER_KWARGS
    assert protocol['contract'] == CONTRACT
    assert protocol['refiner_profiles'] == [list(a) for a in REFINER_PROFILES]
    assert len(protocol['cases']) * 12 == protocol['episodes']
    _check_current_sources(protocol['source_hashes'])
    for name, digest in protocol['source_hashes'].items():
        assert sha(out / 'source' / name) == digest
    return protocol


def initialize(out):
    import torch
    from .learner import IndependentPPO
    global MODELS, OUTPUT
    torch.set_num_threads(1)
    OUTPUT = Path(out)
    protocol = verify_protocol(OUTPUT)
    MODELS = {}
    for key, record in protocol['policies'].items():
        assert sha(ROOT / record['path']) == record['sha256']
        model = IndependentPPO.load(ROOT / record['path'], device='cpu')
        assert model.observation_space.shape == (55,)
        assert model.action_space.shape == (8,)
        MODELS[key] = model


def refiner(c, ctx):
    """Four fixed signed profiles; same first-admissible-scale owner rule."""
    action = np.zeros(8)
    reference_cost = float(np.mean([v[0] for v in ctx.reference_values]))
    best = reference_cost
    report = dict(score_evaluations=0, profiles_checked=0, selected_profile=None,
                  selected_projection_scale=0., reference_cost=reference_cost)
    if not ctx.eligible:
        report['reason'] = 'analytical_guard_or_safety_active'
        return action, report
    for index, profile in enumerate(REFINER_PROFILES):
        report['profiles_checked'] += 1
        for scale in c.projection_scales:
            score = c.score_candidate(ctx, profile, scale)
            report['score_evaluations'] += 1
            if score.admissible and score.cost < reference_cost - 1e-8:
                # finish also stops at the first admitted scale, even if that
                # scale has no first-command change. Do not skip past it.
                if abs(score.first - ctx.reference_first) > 1e-12 and score.cost < best:
                    action = np.asarray(profile, float)
                    best = score.cost
                    report.update(selected_profile=index, selected_projection_scale=scale)
                break
    report.update(selected_model_cost=best, reason='fixed_causal_model_profiles')
    return action, report


def context_record(ctx):
    return dict(
        now=ctx.now, observed_s=ctx.observed_s, wall_started=ctx.wall_started,
        previous=asdict(ctx.previous), state=ctx.state,
        reference_first=ctx.reference_first, reference_residual=ctx.reference_residual,
        acceleration=ctx.acceleration, reference_plan=ctx.reference_plan,
        planned=ctx.planned, models=ctx.models, vehicles=ctx.vehicles,
        reference_values=ctx.reference_values, lqr_values=ctx.lqr_values,
        anchor_features=ctx.anchor_features, eligible=ctx.eligible,
    )


def run(case, mode, seed, models=None):
    """A complete 120-tick task; stop only on a real collision/corridor failure."""
    assert seed in seeds_for(mode)
    models = MODELS if models is None else models
    adaptive = mode != 'lqr'
    params = dict(PARAMS, **CONTROLLER_KWARGS)
    params.update(adaptive=adaptive, mpc=adaptive)
    c, clock, ego, npcs, net = setup(
        case, 'deterministic' if adaptive else 'lqr', controller_class(),
        params, grid=adaptive,
    )
    shadow, sclock, sego, _, snet = setup(
        case, 'lqr', SafeController, dict(PARAMS, adaptive=False, mpc=False), grid=False,
    )
    sequence = 0
    last = np.zeros(8)
    running = RunningStats()
    squared = heading_sq = rate_sq = shadow_heading = shadow_rate = 0.
    rows = []
    for tick in range(HORIZON):
        now = tick * .05
        clock.now = sclock.now = now
        net.emit(now, ego, npcs, c.inbox)
        snet.emit(now, sego, npcs, shadow.inbox)
        ctx = c.prepare(now)
        query, valid = observe(c, ctx, running, last)
        action = np.zeros(8)
        diagnostic = {}
        proposal = None
        if valid and mode in LEARNED:
            action, _ = models[f'{mode}-{seed}'].predict(query, deterministic=True)
            action = np.clip(np.asarray(action, float).ravel(), -1, 1)
            assert action.shape == (8,) and np.isfinite(action).all()
        elif valid and mode == 'refiner':
            action, diagnostic = refiner(c, ctx)
        if valid and mode not in ('lqr', 'adaptive'):
            sequence += 1
            proposal = CorrectionProposal(sequence, ctx.observed_s, now,
                                          ctx.wall_started, tuple(action))
            running.note_proposal(proposal)
            last = action.copy()
        decision = c.finish(ctx, proposal)
        shadow_decision = shadow.decide(now)
        before, sbefore = ego.copy(), sego.copy()
        previous, sprevious = c.applied, shadow.applied
        ego = c.apply(now, ego, case['stiffness'])
        sego = shadow.apply(now, sego, case['stiffness'])
        move_npcs(npcs, .05, c.route, case['scenario'])
        truth = truth_metrics(ego, npcs, c.route, c.cfg)
        shadow_truth = truth_metrics(sego, npcs, shadow.route, shadow.cfg)
        rate = (c.applied.steering - previous.steering) / .05
        srate = (shadow.applied.steering - sprevious.steering) / .05
        failed = bool(truth['collision'] or truth['corridor_exceeded'])
        primary, squared = rmse_reward(squared, truth['error'], tick + 1, failed)
        heading_sq += truth['heading_error'] ** 2
        rate_sq += rate ** 2
        shadow_heading += shadow_truth['heading_error'] ** 2
        shadow_rate += srate ** 2
        done = failed or tick == HORIZON - 1
        parts = dict(rmse_reward=primary)
        if done:
            parts.update(terminal_constraints(
                heading_sq, rate_sq, float(ego[0]),
                dict(heading_sq=shadow_heading, rate_sq=shadow_rate, progress_m=float(sego[0])), failed,
            ))
        row = dict(
            **decision, **truth, episode_id=0, case=case, mode=mode, seed=seed,
            tick=tick, time_s=now, observation=query, observation_valid=valid,
            label=action, context=context_record(ctx), refiner=diagnostic,
            state_before=before, state_after=ego.copy(),
            shadow_before=sbefore, shadow_after=sego.copy(), shadow_truth=shadow_truth,
            shadow_decision=shadow_decision, shadow_steering=shadow.applied.steering,
            shadow_accel=shadow.applied.accel, shadow_rate=srate,
            npc_truth={name: z.copy() for name, z in npcs.items()},
            applied_steering=c.applied.steering, applied_accel=c.applied.accel,
            steering_rate=rate, score_error_sq=squared, heading_energy=heading_sq,
            rate_energy=rate_sq, reward_parts=parts, reward=float(sum(parts.values())),
            proposal=None if proposal is None else asdict(proposal),
            terminated=done, truncated=False,
            terminal_reason='failure' if failed else ('horizon' if done else ''),
        )
        rows.append(row)
        if done:
            break
    count = len(rows)
    record = dict(
        case=case, mode=mode, seed=seed, ticks=count, expected_ticks=HORIZON,
        rmse_m=math.sqrt((sum(r['error'] ** 2 for r in rows) + (HORIZON-count)*6.25) / HORIZON),
        heading_rms=math.sqrt(heading_sq / count), rate_rms=math.sqrt(rate_sq / count),
        progress_m=float(ego[0]), failed=bool(rows[-1]['terminal_reason'] == 'failure'),
        collisions=sum(bool(r['collision']) for r in rows),
        corridor_failures=sum(bool(r['corridor_exceeded']) for r in rows),
        selected_ticks=sum(bool(r['sequence_plan_selected']) for r in rows),
        refiner_evaluations=sum(r['refiner'].get('score_evaluations', 0) for r in rows),
        primary_reward=sum(r['reward_parts']['rmse_reward'] for r in rows),
        total_reward=sum(r['reward'] for r in rows),
        full_episode_score=True, synthetic_clock=True,
    )
    assert record['rmse_m'] == math.sqrt(squared / HORIZON)
    return record, rows


def worker(job):
    case, mode, seed = job
    path = OUTPUT / f'{case["id"]:03d}-{mode}-{seed}.jsonl'
    record_path = path.with_suffix('.json')
    protocol_hash = sha(OUTPUT / 'protocol.json')
    if record_path.exists():
        record = json.loads(record_path.read_text())
        assert record['case'] == case and record['mode'] == mode and record['seed'] == seed
        assert record['raw_sha256'] == sha(path) and record['protocol_sha256'] == protocol_hash
        return record
    assert not path.exists(), ('incomplete raw outcome retained; refusing overwrite', path)
    record, rows = run(case, mode, seed)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(jsonable(row), allow_nan=False) + '\n')
    record.update(raw_sha256=sha(path), protocol_sha256=protocol_hash)
    write(record_path, record)
    return record


def assess(records, bootstrap_seed):
    lookup = {(r['case']['id'], r['mode'], r['seed']): r for r in records}
    ids = sorted({r['case']['id'] for r in records})
    assert len(records) == len(lookup) == 12 * len(ids)
    cases = {}
    for case_id in ids:
        case = lookup[(case_id, 'lqr', 0)]['case']
        cases[case_id] = case
        for mode in MODES:
            for seed in seeds_for(mode):
                row = lookup[(case_id, mode, seed)]
                assert row['case'] == case
                assert row['expected_ticks'] == HORIZON and 1 <= row['ticks'] <= HORIZON
                assert 0 <= row['collisions'] <= row['ticks']
                assert 0 <= row['corridor_failures'] <= row['ticks']
                assert bool(row['failed']) == (row['ticks'] < HORIZON or row['collisions'] > 0 or row['corridor_failures'] > 0)
                assert np.isfinite([row[k] for k in ('rmse_m', 'heading_rms', 'rate_rms', 'progress_m')]).all()
                assert row['rmse_m'] >= 0 and row['heading_rms'] >= 0 and row['rate_rms'] >= 0
    groups = {}
    for case_id, case in cases.items():
        groups.setdefault((case['scenario'], case['speed'], case['delay']), []).append(case_id)
    assert set(groups) == set(STRATA), 'all 36 registered strata must remain in assessment'
    assert len({len(v) for v in groups.values()}) == 1
    for case_ids in groups.values():
        cells = {(cases[i]['mirror'], cases[i]['replica']) for i in case_ids}
        assert len(cells) == len(case_ids) and len(case_ids) in (2, 4)
        assert cells == {(mirror, replica) for mirror in (-1, 1) for replica in range(len(case_ids)//2)}
    # One resampled row is a whole stratum: both mirrors, all state replicas,
    # all policies and their matched references stay together.
    draw = np.random.default_rng(bootstrap_seed).integers(36, size=(5000, 36))
    metrics = {mode: {key: float(np.mean([r[key] for r in records if r['mode'] == mode]))
                      for key in ('rmse_m', 'heading_rms', 'rate_rms', 'progress_m')}
               for mode in MODES}
    comparisons = {}
    for mode in MODES:
        if mode == 'ppo':
            continue
        pairs = []
        for group in STRATA:
            case_ids = groups[group]
            reference = [lookup[(i, mode, seed)]['rmse_m'] for i in case_ids for seed in seeds_for(mode)]
            candidate = [lookup[(i, 'ppo', seed)]['rmse_m'] for i in case_ids for seed in SEEDS]
            pairs.append([np.mean(reference), np.mean(candidate)])
        pairs = np.asarray(pairs)
        mean = pairs.mean(axis=0)
        assert mean[0] > 0
        sampled = pairs[draw].mean(axis=1)
        interval = np.quantile(100 * (1 - sampled[:, 1] / sampled[:, 0]), [.025, .975])
        comparisons[mode] = dict(
            gain_percent=float(100 * (1 - mean[1]/mean[0])), ci95_percent=interval.tolist(),
            clusters=36, bootstrap_draws=5000, bootstrap_seed=bootstrap_seed,
            conditional_on_three_trained_policies=True,
            heading_ratio=metrics['ppo']['heading_rms']/max(metrics[mode]['heading_rms'], 1e-300),
            rate_ratio=metrics['ppo']['rate_rms']/max(metrics[mode]['rate_rms'], 1e-300),
            minimum_progress_ratio=min(
                lookup[(i, 'ppo', seed)]['progress_m'] /
                np.mean([lookup[(i, mode, s)]['progress_m'] for s in seeds_for(mode)])
                for i in ids for seed in SEEDS),
        )
    reasons = []
    actors = {}
    base = [lookup[(i, 'lqr', 0)] for i in ids]
    assert all(r['progress_m'] > 0 for r in base)
    mean_heading = float(np.mean([r['heading_rms'] for r in base]))
    mean_rate = float(np.mean([r['rate_rms'] for r in base]))
    assert mean_heading > 0 and mean_rate > 0
    for seed in SEEDS:
        rows = [lookup[(i, 'ppo', seed)] for i in ids]
        headings = float(np.mean([r['heading_rms'] for r in rows]))
        rates = float(np.mean([r['rate_rms'] for r in rows]))
        minimum_progress = min(r['progress_m']/b['progress_m'] for r, b in zip(rows, base))
        failures = sum(bool(r['failed']) for r in rows)
        collisions = sum(r['collisions'] for r in rows)
        corridor = sum(r['corridor_failures'] for r in rows)
        actors[str(seed)] = dict(
            mean_rmse_m=float(np.mean([r['rmse_m'] for r in rows])),
            gain_vs_adaptive_percent=float(100*(1-np.mean([r['rmse_m'] for r in rows])/metrics['adaptive']['rmse_m'])),
            failures=failures, collisions=collisions, corridor_failures=corridor,
            selected_ticks=sum(r['selected_ticks'] for r in rows),
            heading_ratio_to_lqr=headings/mean_heading, rate_ratio_to_lqr=rates/mean_rate,
            minimum_progress_ratio_to_lqr=minimum_progress,
            safety_passed=failures == collisions == corridor == 0,
            progress_passed=all(r['progress_m'] >= .99*b['progress_m'] for r, b in zip(rows, base)),
            heading_passed=headings <= 1.1*mean_heading,
            rate_passed=rates <= 1.1*mean_rate,
        )
        for key in ('safety', 'progress', 'heading', 'rate'):
            if not actors[str(seed)][key + '_passed']:
                reasons.append(f'actor_{seed}_{key}')
    mean_passed = comparisons['adaptive']['gain_percent'] >= 10.
    lower_bound_passed = comparisons['adaptive']['ci95_percent'][0] >= 10.
    if not mean_passed:
        reasons.append('requested_10_mean_gain')
    for mode in ('lqr', 'adaptive', 'bc', 'continued_bc', 'refiner'):
        if comparisons[mode]['ci95_percent'][0] <= 0.:
            reasons.append('confidence_' + mode)
    return dict(
        episodes=len(records), cases=len(ids), metrics=metrics, comparisons=comparisons,
        actors=actors, reasons=reasons,
        requested_10_mean_passed=mean_passed,
        adaptive_ci_lower_at_least_10=lower_bound_passed,
        numerical_qualification_passed=not reasons,
        inferential_at_least_10_passed=not reasons and lower_bound_passed,
        failures={mode: sum(bool(r['failed']) for r in records if r['mode'] == mode) for mode in MODES},
        collisions={mode: sum(r['collisions'] for r in records if r['mode'] == mode) for mode in MODES},
        corridor_failures={mode: sum(r['corridor_failures'] for r in records if r['mode'] == mode) for mode in MODES},
        runtime_validated=False, native_transfer_validated=False,
        overall_qualified=False,
        scope='Synthetic-clock complete-episode Python evaluation only; timing and native transfer remain separate gates.',
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=tuple(COHORTS))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    out = DATA / args.stage
    protocol = verify_protocol(out) if args.resume else prepare(args.stage)
    jobs = [(case, mode, seed) for case in protocol['cases'] for mode in MODES for seed in seeds_for(mode)]
    assert len(jobs) == protocol['episodes']
    records, errors = [], []
    with ProcessPoolExecutor(max_workers=3, mp_context=mp.get_context('spawn'),
                             initializer=initialize, initargs=(str(out),)) as pool:
        futures = {pool.submit(worker, job): job for job in jobs}
        for future in as_completed(futures):
            try:
                records.append(future.result())
            except Exception as exc:
                case, mode, seed = futures[future]
                error = dict(case=case, mode=mode, seed=seed, error_type=type(exc).__name__, error=str(exc))
                errors.append(error)
                write(out / f'{case["id"]:03d}-{mode}-{seed}.error.json', error)
            if (len(records)+len(errors)) % 24 == 0:
                print('V13', args.stage, len(records), '/', len(jobs), 'errors', len(errors), flush=True)
    records.sort(key=lambda r: (r['case']['id'], r['mode'], r['seed']))
    _check_current_sources(protocol['source_hashes'])
    if errors:
        write(out / 'partial-summary.json', records)
        write(out / 'execution-errors.json', dict(errors=errors, overall_qualified=False))
        raise RuntimeError(f'{len(errors)} execution errors retained; no complete-cohort assessment')
    write(out / 'summary.json', records)
    write(out / 'assessment.json', assess(records, protocol['bootstrap_seed']))
    print('V13 COMPLETE', args.stage, len(records), 'matched whole episodes retained', flush=True)


if __name__ == '__main__':
    main()
