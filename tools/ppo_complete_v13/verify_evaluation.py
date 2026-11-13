"""Independent physical/action/statistical audit of the frozen Python cohorts.

Only an already-created cohort is inspected. Import does not draw either
prospective namespace. Every registered role/case remains in paired arithmetic.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import math
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np

from integrations.unified_lans.physics import Command, Config, advance
from integrations.unified_lans.simulation import move_npcs, truth_metrics
from . import evaluate
from .learning import ROOT, DATA, CONTRACT
from .train import SEEDS
from .verify_training import digest, read, write, equal, semantic_equal, initial_truth, bounded

MODELS = {}
OUTPUT = None


def initialize(folder):
    import torch
    from .learner import IndependentPPO
    global MODELS, OUTPUT
    torch.set_num_threads(1)
    OUTPUT = Path(folder)
    p = evaluate.verify_protocol(OUTPUT)
    MODELS = {name: IndependentPPO.load(ROOT/r['path'], device='cpu') for name, r in p['policies'].items()}


def physical_record(meta, rows):
    """Separate original Python physics/reward arithmetic on bounded raw inputs."""
    case = meta['case']
    route, state, npcs = initial_truth(case)
    shadow = state.copy()
    cfg = Config(horizon=2.)
    issued = applied = shadow_issued = shadow_applied = Command()
    pending, shadow_pending = [], []
    sse = heading = rate_energy = shadow_heading = shadow_rate_energy = primary_total = total_reward = 0.
    n = len(rows)
    assert n == meta['ticks'] and 1 <= n <= 120 and meta['expected_ticks'] == 120
    for tick, row in enumerate(rows):
        assert row['case'] == case and row['episode_id'] == 0 and row['tick'] == tick
        assert row['mode'] == meta['mode'] and row['seed'] == meta['seed']
        equal(row['time_s'], tick*.05, 'evaluation time')
        equal(row['state_before'], state, 'independent plant before')
        equal(row['shadow_before'], shadow, 'independent shadow before')
        command = Command(row['issued_steering'], row['issued_accel'])
        shadow_command = Command(row['shadow_decision']['issued_steering'], row['shadow_decision']['issued_accel'])
        bounded(command, issued)
        bounded(shadow_command, shadow_issued)
        issued, shadow_issued = command, shadow_command
        pending.append((tick*.05+case['delay'], command))
        shadow_pending.append((tick*.05+case['delay'], shadow_command))
        previous, shadow_previous = applied, shadow_applied
        while pending and pending[0][0] <= tick*.05+1e-9:
            _, applied = pending.pop(0)
        while shadow_pending and shadow_pending[0][0] <= tick*.05+1e-9:
            _, shadow_applied = shadow_pending.pop(0)
        equal([row['applied_steering'], row['applied_accel']], [applied.steering, applied.accel], 'evaluation FIFO')
        equal([row['shadow_steering'], row['shadow_accel']], [shadow_applied.steering, shadow_applied.accel], 'shadow FIFO')
        state = advance(state, applied, .05, case['stiffness'])
        shadow = advance(shadow, shadow_applied, .05, case['stiffness'])
        equal(row['state_after'], state, 'independent evaluation RK4')
        equal(row['shadow_after'], shadow, 'independent shadow RK4')
        move_npcs(npcs, .05, route, case['scenario'])
        equal(row['npc_truth'], npcs, 'independent evaluation traffic')
        truth = truth_metrics(state, npcs, route, cfg)
        shadow_truth = truth_metrics(shadow, npcs, route, cfg)
        for name, value in truth.items():
            equal(row[name], value, 'independent evaluation truth.'+name)
        equal(row['shadow_truth'], shadow_truth, 'independent evaluation shadow truth')
        rate = (applied.steering-previous.steering)/.05
        shadow_rate = (shadow_applied.steering-shadow_previous.steering)/.05
        equal(row['steering_rate'], rate)
        equal(row['shadow_rate'], shadow_rate)
        failed = bool(truth['collision'] or truth['corridor_exceeded'])
        if tick < n-1:
            assert not failed
        old = sse
        sse += truth['error']**2+(119-tick)*6.25*failed
        primary = 100*(math.sqrt((old+1e-12)/120)-math.sqrt((sse+1e-12)/120))
        heading += truth['heading_error']**2
        rate_energy += rate*rate
        shadow_heading += shadow_truth['heading_error']**2
        shadow_rate_energy += shadow_rate*shadow_rate
        done = failed or tick == 119
        parts = dict(rmse_reward=primary)
        if done:
            hr = math.sqrt(heading/max(shadow_heading, 1e-8))
            rr = math.sqrt(rate_energy/max(shadow_rate_energy, 1e-8))
            progress = state[0]/max(shadow[0], 1e-6)
            parts.update(heading_penalty=-20*max(0., hr-1.05), rate_penalty=-20*max(0., rr-1.05),
                progress_penalty=-100*max(0., .995-progress)-5*(progress < .99), failure_penalty=-20.*failed)
        equal(row['score_error_sq'], sse)
        equal(row['heading_energy'], heading)
        equal(row['rate_energy'], rate_energy)
        equal(row['reward_parts'], parts)
        equal(row['reward'], sum(parts.values()))
        assert row['terminated'] == done and row['truncated'] is False
        assert row['terminal_reason'] == ('failure' if failed else 'horizon' if done else '')
        primary_total += primary
        total_reward += row['reward']
    assert rows[-1]['terminated'] and (n == 120 or rows[-1]['collision'] or rows[-1]['corridor_exceeded'])
    recomputed = dict(rmse_m=math.sqrt(sse/120), heading_rms=math.sqrt(heading/n),
        rate_rms=math.sqrt(rate_energy/n), progress_m=float(state[0]),
        failed=bool(rows[-1]['collision'] or rows[-1]['corridor_exceeded']),
        collisions=sum(r['collision'] for r in rows), corridor_failures=sum(r['corridor_exceeded'] for r in rows),
        selected_ticks=sum(bool(r['sequence_plan_selected']) for r in rows),
        primary_reward=primary_total, total_reward=total_reward)
    for name, value in recomputed.items():
        equal(meta[name], value, 'independent episode summary.'+name)
    equal(primary_total, 100*(math.sqrt(1e-12/120)-math.sqrt((sse+1e-12)/120)), 'evaluation primary telescoping', atol=1e-8)
    return recomputed


def episode(meta):
    path = OUTPUT/f'{meta["case"]["id"]:03d}-{meta["mode"]}-{meta["seed"]}.jsonl'
    assert digest(path) == meta['raw_sha256']
    assert read(path.with_suffix('.json')) == meta
    assert meta['protocol_sha256'] == digest(OUTPUT/'protocol.json')
    rows = [json.loads(line) for line in path.open()]
    assert rows
    # Replay the source-pinned causal owner and every frozen deterministic
    # policy/refiner decision; independent plant/reward arithmetic follows.
    regenerated_meta, regenerated_rows = evaluate.run(meta['case'], meta['mode'], meta['seed'], MODELS)
    assert len(rows) == len(regenerated_rows)
    semantic_equal(meta, regenerated_meta, 'full evaluation summary')
    for actual, regenerated in zip(rows, regenerated_rows):
        semantic_equal(actual, regenerated, 'full causal evaluation decision')
        if meta['mode'] in evaluate.LEARNED:
            predicted = MODELS[f'{meta["mode"]}-{meta["seed"]}'].predict(np.asarray(actual['observation'], np.float32), deterministic=True)[0]
            equal(actual['label'], predicted, 'frozen deterministic evaluation action', atol=1e-7)
    values = physical_record(meta, rows)
    return dict(case_id=meta['case']['id'], mode=meta['mode'], seed=meta['seed'], ticks=len(rows),
        failed=values['failed'], selected_ticks=values['selected_ticks'], raw_sha256=meta['raw_sha256'])


def statistics(records, assessment, protocol):
    """Independently reconstruct paired strata, actor gates and confidence bounds."""
    cases = protocol['cases']
    lookup = {(r['case']['id'], r['mode'], r['seed']): r for r in records}
    expected = {(c['id'], mode, seed) for c in cases for mode in evaluate.MODES for seed in evaluate.seeds_for(mode)}
    assert len(records) == len(lookup) == len(expected) and set(lookup) == expected
    groups = {}
    for case in cases:
        groups.setdefault((case['scenario'], case['speed'], case['delay']), []).append(case['id'])
        for mode in evaluate.MODES:
            for seed in evaluate.seeds_for(mode):
                assert lookup[(case['id'], mode, seed)]['case'] == case
    assert len(groups) == 36 and set(groups) == set(evaluate.STRATA)
    assert len({len(ids) for ids in groups.values()}) == 1
    metrics = {}
    for mode in evaluate.MODES:
        rr = [r for r in records if r['mode'] == mode]
        metrics[mode] = {key: float(np.mean([r[key] for r in rr])) for key in ('rmse_m', 'heading_rms', 'rate_rms', 'progress_m')}
        equal(assessment['metrics'][mode], metrics[mode], 'independent role means')
        for name, field in (('failures', 'failed'), ('collisions', 'collisions'), ('corridor_failures', 'corridor_failures')):
            assert assessment[name][mode] == sum(r[field] for r in rr)
    draw = np.random.default_rng(protocol['bootstrap_seed']).integers(36, size=(5000, 36))
    for mode in evaluate.MODES:
        if mode == 'ppo':
            continue
        pairs = np.array([[np.mean([lookup[(i, mode, s)]['rmse_m'] for i in groups[group] for s in evaluate.seeds_for(mode)]),
            np.mean([lookup[(i, 'ppo', s)]['rmse_m'] for i in groups[group] for s in SEEDS])] for group in evaluate.STRATA])
        average = pairs.mean(axis=0)
        sample = pairs[draw].mean(axis=1)
        current = assessment['comparisons'][mode]
        assert current['clusters'] == 36 and current['bootstrap_draws'] == 5000 and current['bootstrap_seed'] == protocol['bootstrap_seed']
        assert current['conditional_on_three_trained_policies']
        equal(current['gain_percent'], 100*(1-average[1]/average[0]))
        equal(current['ci95_percent'], np.quantile(100*(1-sample[:, 1]/sample[:, 0]), [.025, .975]))
        equal(current['heading_ratio'], metrics['ppo']['heading_rms']/max(metrics[mode]['heading_rms'], 1e-300))
        equal(current['rate_ratio'], metrics['ppo']['rate_rms']/max(metrics[mode]['rate_rms'], 1e-300))
        minimum = min(lookup[(c['id'], 'ppo', s)]['progress_m']/np.mean([
            lookup[(c['id'], mode, k)]['progress_m'] for k in evaluate.seeds_for(mode)]) for c in cases for s in SEEDS)
        equal(current['minimum_progress_ratio'], minimum)
    reasons = []
    for seed in SEEDS:
        rows = [lookup[(c['id'], 'ppo', seed)] for c in cases]
        base = [lookup[(c['id'], 'lqr', 0)] for c in cases]
        assert all(r['progress_m'] > 0 for r in base)
        actual = assessment['actors'][str(seed)]
        flags = dict(safety=not any(r['failed'] or r['collisions'] or r['corridor_failures'] for r in rows),
            progress=all(r['progress_m'] >= .99*b['progress_m'] for r, b in zip(rows, base)),
            heading=np.mean([r['heading_rms'] for r in rows]) <= 1.1*np.mean([b['heading_rms'] for b in base]),
            rate=np.mean([r['rate_rms'] for r in rows]) <= 1.1*np.mean([b['rate_rms'] for b in base]))
        for key, flag in flags.items():
            assert actual[key+'_passed'] == flag
            if not flag:
                reasons.append(f'actor_{seed}_{key}')
        expected_actor = dict(mean_rmse_m=float(np.mean([r['rmse_m'] for r in rows])),
            gain_vs_adaptive_percent=100*(1-np.mean([r['rmse_m'] for r in rows])/metrics['adaptive']['rmse_m']),
            failures=sum(r['failed'] for r in rows), collisions=sum(r['collisions'] for r in rows),
            corridor_failures=sum(r['corridor_failures'] for r in rows), selected_ticks=sum(r['selected_ticks'] for r in rows),
            heading_ratio_to_lqr=np.mean([r['heading_rms'] for r in rows])/np.mean([r['heading_rms'] for r in base]),
            rate_ratio_to_lqr=np.mean([r['rate_rms'] for r in rows])/np.mean([r['rate_rms'] for r in base]),
            minimum_progress_ratio_to_lqr=min(r['progress_m']/b['progress_m'] for r, b in zip(rows, base)))
        for key, value in expected_actor.items():
            equal(actual[key], value, 'independent per-actor summary')
    mean_pass = assessment['comparisons']['adaptive']['gain_percent'] >= 10
    lower_pass = assessment['comparisons']['adaptive']['ci95_percent'][0] >= 10
    if not mean_pass:
        reasons.append('requested_10_mean_gain')
    for mode in ('lqr', 'adaptive', 'bc', 'continued_bc', 'refiner'):
        if assessment['comparisons'][mode]['ci95_percent'][0] <= 0:
            reasons.append('confidence_'+mode)
    assert assessment['reasons'] == reasons
    assert assessment['requested_10_mean_passed'] == mean_pass and assessment['adaptive_ci_lower_at_least_10'] == lower_pass
    assert assessment['numerical_qualification_passed'] == (not reasons)
    assert assessment['inferential_at_least_10_passed'] == (not reasons and lower_pass)
    assert assessment['episodes'] == len(records) and assessment['cases'] == len(cases)
    assert assessment['runtime_validated'] is assessment['native_transfer_validated'] is assessment['overall_qualified'] is False
    return dict(strata=36, bootstrap_draws=5000, bootstrap_seed=protocol['bootstrap_seed'],
        all_actors_and_failures_retained=True, reasons=reasons)


def verify_cohort(stage, reuse=False, workers=3):
    assert stage in ('validation', 'final')
    assert type(workers) is int and 1 <= workers <= 3, 'Choose1..3 independent audit workers'
    folder = DATA/stage
    protocol = evaluate.verify_protocol(folder)  # Checks every endpoint/control before any RNG draw.
    settings = evaluate.COHORTS[stage]
    for name, value in settings.items():
        assert protocol[name] == value
    expected_cases = evaluate.draw_cases(np.random.default_rng(settings['case_seed']), settings['draws'], f'v13_prospective_{stage}')
    assert protocol['cases'] == expected_cases and protocol['episodes'] == (864 if stage == 'validation' else 1728)
    assert protocol['modes'] == list(evaluate.MODES) and protocol['seeds'] == list(SEEDS)
    assert protocol['bootstrap_draws'] == 5000 and protocol['contract'] == CONTRACT
    assert protocol['target_increment_percent'] == 10.
    assert protocol['score_horizon_ticks'] == 120 and protocol['unrun_tick_error_sq'] == 6.25
    if stage == 'final':
        for field, filename in (('summary_sha256', 'summary.json'), ('assessment_sha256', 'assessment.json'), ('protocol_sha256', 'protocol.json')):
            assert protocol['validation_input'][field] == digest(DATA/'validation'/filename)
    records, assessment = read(folder/'summary.json'), read(folder/'assessment.json')
    assert len(records) == protocol['episodes'] and len({(r['case']['id'], r['mode'], r['seed']) for r in records}) == len(records)
    assert not (folder/'execution-errors.json').exists(), 'Unresolved execution errors cannot be omitted'
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in [folder/'protocol.json', folder/'summary.json', folder/'assessment.json', Path(__file__)]}
    for record in records:
        assert record['case'] == protocol['cases'][record['case']['id']]
        path = folder/f'{record["case"]["id"]:03d}-{record["mode"]}-{record["seed"]}.jsonl'
        for source in (path, path.with_suffix('.json')):
            inputs[str(source.relative_to(ROOT))] = digest(source)
    for name, expected in protocol['source_hashes'].items():
        assert digest(ROOT/name) == expected
        inputs[name] = expected
        inputs[str((folder/'source'/name).relative_to(ROOT))] = expected
    for record in protocol['policies'].values():
        inputs[record['path']] = record['sha256']
        inputs[record['manifest_path']] = record['manifest_sha256']
    cache = folder/'independent-verification.json'
    if reuse and cache.exists():
        cached = read(cache)
        assert cached['passed'] and cached['input_hashes'] == inputs
        return cached
    audited = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context('spawn'), initializer=initialize, initargs=(str(folder),)) as pool:
        for future in as_completed([pool.submit(episode, r) for r in records]):
            audited.append(future.result())
            if len(audited) % 72 == 0:
                print('V13 INDEPENDENT EVALUATION REPLAY', stage, len(audited), '/', len(records), flush=True)
    summary = statistics(records, assessment, protocol)
    for name, expected in inputs.items():
        assert digest(ROOT/name) == expected, ('Evaluation input changed during replay', name)
    result = dict(passed=True, stage=stage, episodes=len(audited), ticks=sum(r['ticks'] for r in audited),
        failed_episodes=sum(r['failed'] for r in audited), selected_ticks=sum(r['selected_ticks'] for r in audited),
        full_causal_controller_query_guard_action_replayed=True, independent_plant_shadow_reward_replayed=True,
        statistics=summary, numerical_qualification_passed=assessment['numerical_qualification_passed'],
        inferential_at_least_10_passed=assessment['inferential_at_least_10_passed'], overall_qualified=False,
        input_hashes=inputs, verifier_sha256=digest(__file__))
    write(cache, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('validation', 'final'))
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    result = verify_cohort(args.stage, reuse=args.reuse, workers=args.workers)
    print(json.dumps(dict(passed=result['passed'], stage=args.stage,
        episodes=result['episodes'], numerical_qualification_passed=result['numerical_qualification_passed'],
        overall_qualified=False), indent=2), flush=True)


if __name__ == '__main__':
    main()
