"""Complete-stage V13 numerical evidence audit, separate from qualification.

Missing stages are reported explicitly. This never launches training, draws
unopened prospective cases, reruns observed timing or starts Webots. Full
deterministic Python evaluation is replayed; full stochastic-training controller
replay is an optional additional scope. Failed outcomes remain valid evidence.
"""
from pathlib import Path
import argparse
import json
import math
import re
import shutil
import subprocess
import sys

import numpy as np

from integrations.unified_lans.physics import Command, Config, advance
from integrations.unified_lans.simulation import move_npcs, truth_metrics
from .learning import ROOT, DATA
from .train import SEEDS
from .verify_training import digest, read, write, equal, source_protocol, initial_truth, bounded, replay_trace

STAGES = dict(safety=('episodes', 288), teacher=('episodes', 144), dataset=('samples', 8640),
    training=('steps', 196608), validation=('episodes', 864), final=('episodes', 1728),
    runtime=('episodes', 180), native=('episodes', 120))


class IncompleteEvidence(RuntimeError):
    pass


def require(paths):
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError('Required evidence missing: '+', '.join(missing))


def pinned_inputs(paths, source_hashes=None):
    result = {str(Path(p).relative_to(ROOT)): digest(p) for p in paths}
    for name, expected in (source_hashes or {}).items():
        assert digest(ROOT/name) == expected, ('Active mathematical source changed', name)
        result[name] = expected
    return result


def evidence_dependencies(folder):
    """Pin consulted unit bytes before allowing any previous proof reuse.

    A raw-pose hash alone cannot attest the accompanying native world, PROTOs,
    initialization or common scene calibration. Generated caches are outside
    evidence; every regular non-symlink file in the measured unit is retained.
    """
    ignored = {'.pyc', '.pyo', '.nbc', '.nbi'}
    return [p for p in Path(folder).rglob('*') if p.is_file() and not p.is_symlink()
        and p.suffix not in ignored and '__pycache__' not in p.parts]


def check_inputs(inputs):
    for name, expected in inputs.items():
        assert digest(ROOT/name) == expected, ('Evidence changed during/after audit', name)


def safety():
    from . import safety_regression
    out = DATA/'safety-development-v2'
    require([out/n for n in ('protocol.json', 'summary.json', 'assessment.json', 'verification.json')])
    p, records, audit = read(out/'protocol.json'), read(out/'summary.json'), read(out/'verification.json')
    assert audit['passed'] and audit['episodes'] == len(records) == 288
    assert audit['auditor_source_sha256'] == digest(safety_regression.__file__)
    assert audit['summary_sha256'] == digest(out/'summary.json') and audit['assessment_sha256'] == digest(out/'assessment.json')
    assert audit['generation_source_hashes'] == p['source_hashes'] and audit['input_hashes'] == p['input_hashes']
    inputs = pinned_inputs([out/n for n in ('protocol.json', 'summary.json', 'assessment.json', 'verification.json')])
    for name, expected in p['source_hashes'].items():
        assert digest(out/'source'/name) == expected
        inputs[str((out/'source'/name).relative_to(ROOT))] = expected
        if name != str(Path(safety_regression.__file__).relative_to(ROOT)):
            assert digest(ROOT/name) == expected
            inputs[name] = expected
    check_inputs(p['input_hashes'])
    inputs.update(p['input_hashes'])
    for record in records:
        path = out/f'{record["stage"]}-{record["case"]["id"]:03d}-{record["mode"]}.jsonl'
        assert digest(path) == record['raw_sha256'] and read(path.with_suffix('.json')) == record
        inputs.update(pinned_inputs([path, path.with_suffix('.json')]))
    assert read(out/'assessment.json') == safety_regression.assess(records)
    assert len({(r['stage'], r['case']['id'], r['mode']) for r in records}) == 288
    return dict(episodes=288, ticks=audit['ticks'], failures=sum(r['failed'] for r in records),
        certificates=audit['independently_checked_clearance_decisions'], input_hashes=inputs,
        scope='Exact source/input/raw-hash-pinned reuse of the completed independent288-episode physical/certificate replay.')


def teacher(reuse=False):
    out = DATA/'teacher-development72'
    require([out/n for n in ('protocol.json', 'summary.json', 'assessment.json')])
    protocol = source_protocol(out)
    records = read(out/'summary.json')
    assert len(records) == 144 and len(protocol['cases']) == 72
    assert {(r['case']['id'], r['mode']) for r in records} == {(c['id'], mode) for c in protocol['cases'] for mode in ('reference', 'teacher')}
    paths = [out/n for n in ('protocol.json', 'summary.json', 'assessment.json')]+[Path(__file__)]
    for record in records:
        path = out/f'{record["case"]["id"]:03d}-{record["mode"]}.jsonl'
        assert digest(path) == record['raw_sha256']
        paths.append(path)
    inputs = pinned_inputs(paths+evidence_dependencies(out/'source'), protocol['source_hashes'])
    cache = out/'independent-verification.json'
    if reuse and cache.exists():
        result = read(cache)
        assert result['passed'] and result['input_hashes'] == inputs
        return result
    ticks = selected = failures = 0
    for index, record in enumerate(records):
        path = out/f'{record["case"]["id"]:03d}-{record["mode"]}.jsonl'
        replay, _, _ = replay_trace(path, expected_steps=record['ticks'], expected_cases=[record['case']], complete_episodes=1)
        rows = [json.loads(line) for line in path.open()]
        n = len(rows)
        values = dict(rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
            heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),
            rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])), progress_m=rows[-1]['state_after'][0],
            failed=bool(replay['failures']), collisions=sum(r['collision'] for r in rows), selected_ticks=replay['selected_ticks'])
        for name, value in values.items():
            equal(record[name], value, 'teacher independent episode metric')
        ticks += n
        selected += replay['selected_ticks']
        failures += replay['failures']
        if (index+1) % 24 == 0:
            print('V13 TEACHER PHYSICAL REPLAY', index+1, '/144', flush=True)
    reference = [r for r in records if r['mode'] == 'reference']
    learned = [r for r in records if r['mode'] == 'teacher']
    a = read(out/'assessment.json')
    lookup = {r['case']['id']: r for r in reference}
    expected = dict(episodes=144, reference_mean_rmse_m=float(np.mean([r['rmse_m'] for r in reference])),
        teacher_mean_rmse_m=float(np.mean([r['rmse_m'] for r in learned])), failures=failures, selected_ticks=selected,
        heading_ratio=np.mean([r['heading_rms'] for r in learned])/np.mean([r['heading_rms'] for r in reference]),
        rate_ratio=np.mean([r['rate_rms'] for r in learned])/np.mean([r['rate_rms'] for r in reference]),
        minimum_progress_ratio=min(r['progress_m']/lookup[r['case']['id']]['progress_m'] for r in learned))
    expected['gain_percent'] = 100*(1-expected['teacher_mean_rmse_m']/expected['reference_mean_rmse_m'])
    for name, value in expected.items():
        equal(a[name], value)
    check_inputs(inputs)
    result = dict(passed=True, episodes=144, ticks=ticks, failures=failures, selected_ticks=selected,
        input_hashes=inputs, verifier_sha256=digest(__file__), scope='Opened development teacher evidence; not PPO or prospective qualification.')
    write(cache, result)
    return result


def training(reuse=False, full=False, workers=3):
    required = [DATA/f'{folder}/summary.json' for folder in ('policies', 'continued-bc')]
    require(required)
    arguments = [sys.executable, '-m', 'tools.ppo_complete_v13.verify_training', '--workers', str(workers)]
    if reuse:
        arguments.append('--reuse')
    if full:
        arguments.append('--replay-controllers')
    subprocess.run(arguments, cwd=ROOT, check=True)
    out = DATA/'training-verification.json'
    result = read(out)
    assert result['passed'] and result['training_steps'] == 196608
    assert result['verifier_sha256'] == digest(Path(__file__).with_name('verify_training.py'))
    assert not full or result['full_controller_query_guard_replayed']
    check_inputs(result['input_hashes'])
    return dict(steps=196608, shadow_steps=196608,
        failures=result['all_failures_preserved'], full_controller_query_guard_replayed=result['full_controller_query_guard_replayed'],
        input_hashes={**result['input_hashes'], str(out.relative_to(ROOT)): digest(out)},
        scope='Source-pinned physical/shadow/FIFO/NPC/reward plus optimizer audit; full training controller replay explicitly reported.')


def runtime_physics(record):
    path = ROOT/record['raw_path']
    assert digest(path) == record['raw_sha256']
    rows = [json.loads(line) for line in path.open()]
    route, state, npcs = initial_truth(record['case'])
    issued = applied = Command()
    pending = []
    cfg = Config(horizon=2.)
    for tick, row in enumerate(rows):
        assert row['tick'] == tick and row['case'] == record['case']
        equal(row['time_s'], tick*.05)
        equal(row['state_before'], state, 'runtime independent plant before')
        command = Command(row['issued_steering'], row['issued_accel'])
        bounded(command, issued)
        issued = command
        pending.append((tick*.05+record['case']['delay'], command))
        previous = applied
        while pending and pending[0][0] <= tick*.05+1e-9:
            _, applied = pending.pop(0)
        equal([row['applied_steering'], row['applied_accel']], [applied.steering, applied.accel], 'runtime actual FIFO')
        state = advance(state, applied, .05, record['case']['stiffness'])
        equal(row['state_after'], state, 'runtime independent original RK4')
        move_npcs(npcs, .05, route, record['case']['scenario'])
        equal(row['npc_truth'], npcs)
        truth = truth_metrics(state, npcs, route, cfg)
        for name, value in truth.items():
            equal(row[name], value)
        equal(row['steering_rate'], (applied.steering-previous.steering)/.05)
        if tick < len(rows)-1:
            assert not row['collision'] and not row['corridor_exceeded']
    assert len(rows) == record['ticks']
    n = len(rows)
    if n < 120:
        assert rows[-1]['collision'] or rows[-1]['corridor_exceeded']
    metrics = dict(rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
        heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),
        rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])), progress_m=float(state[0]))
    for name, value in metrics.items():
        equal(record[name], value)
    return n


def measured_statistics(records, protocol, assessment):
    from . import complete
    assert assessment == complete.assess_stage(records, protocol, ())
    lookup = {(r['case']['id'], r['mode'], r['seed']): r for r in records}
    assert len(lookup) == len(records) == protocol['expected_episodes']
    groups = {}
    for case in protocol['cases']:
        groups.setdefault((case['scenario'], case['speed'], case['delay']), []).append(case['id'])
    count = 36 if protocol['kind'] == 'runtime' else 12
    assert len(groups) == count
    draw = np.random.default_rng(protocol['bootstrap_seed']).integers(count, size=(5000, count))
    for mode in ('lqr', 'adaptive'):
        pairs = np.asarray([[np.mean([lookup[(i, mode, 0)]['rmse_m'] for i in ids]),
            np.mean([lookup[(i, 'ppo', seed)]['rmse_m'] for i in ids for seed in SEEDS])] for _, ids in sorted(groups.items())])
        mean, sampled = pairs.mean(axis=0), pairs[draw].mean(axis=1)
        current = assessment['comparisons'][mode]
        assert current['clusters'] == count and current['bootstrap_draws'] == 5000
        equal(current['gain_percent'], 100*(1-mean[1]/mean[0]))
        equal(current['ci95_percent'], np.quantile(100*(1-sampled[:, 1]/sampled[:, 0]), [.025, .975]))
    assert assessment['mean_gain_at_least_10'] == (assessment['comparisons']['adaptive']['gain_percent'] >= 10)
    assert assessment['ci_lower_at_least_10'] == (assessment['comparisons']['adaptive']['ci95_percent'][0] >= 10)
    assert assessment['timing_passed'] == (sum(r['ticks'] for r in records) == protocol['expected_owner_slots'] and
        all(r['owner_response_misses'] == r['scheduled_response_misses'] == r['policy_worker_failures'] == 0 for r in records))
    for seed in SEEDS:
        rows = [lookup[(c['id'], 'ppo', seed)] for c in protocol['cases']]
        base = [lookup[(c['id'], 'lqr', 0)] for c in protocol['cases']]
        actor = assessment['actors'][str(seed)]
        assert actor['safety_passed'] == (not any(r['failed'] for r in rows))
        assert actor['progress_passed'] == all(b['progress_m'] > 0 and r['progress_m'] >= .99*b['progress_m'] for r, b in zip(rows, base))
        for key in ('heading', 'rate'):
            assert actor[key+'_passed'] == (np.mean([r[key+'_rms'] for r in rows]) <= 1.1*np.mean([r[key+'_rms'] for r in base]))
    assert assessment['mean_target_qualified'] == (not assessment['reasons'])
    assert assessment['inferential_target_qualified'] == (not assessment['reasons'] and assessment['ci_lower_at_least_10'])


def measured(kind, reuse=False):
    from . import complete, evaluate, runtime, verify_native
    folder = DATA/'completion'/kind
    require([folder/n for n in ('protocol.json', 'summary.json', 'assessment.json', 'journal.jsonl')])
    protocol, summary, assessment = (read(folder/n) for n in ('protocol.json', 'summary.json', 'assessment.json'))
    complete.check_freeze(protocol, folder)
    assert protocol['kind'] == kind and protocol['policies'] == evaluate.frozen_policies()
    assert protocol['roles'] == [list(r) for r in complete.ROLES]
    base = read(DATA/('validation' if kind == 'runtime' else 'final')/'protocol.json')['cases']
    assert protocol['cases'] == complete.select_cases(base, kind)
    assert protocol['expected_episodes'] == (180 if kind == 'runtime' else 120)
    assert protocol['bootstrap_seed'] == (2134155 if kind == 'runtime' else 2134156) and protocol['bootstrap_draws'] == 5000
    assert summary['protocol_sha256'] == digest(folder/'protocol.json')
    if summary['execution_errors'] or len(summary['records']) != protocol['expected_episodes']:
        raise IncompleteEvidence(f'{kind}: {len(summary["records"])}/{protocol["expected_episodes"]} episodes; {len(summary["execution_errors"])} execution errors retained')
    records = summary['records']
    assert summary['assessment'] == assessment
    inputs = pinned_inputs([folder/n for n in ('protocol.json', 'summary.json', 'assessment.json', 'journal.jsonl')]+[Path(__file__)], protocol['source_hashes'])
    inputs.update(protocol['input_hashes'])
    for record in records:
        for path_name, sha_name in (('raw_path', 'raw_sha256'), ('verification_path', 'verification_sha256')):
            assert digest(ROOT/record[path_name]) == record[sha_name]
            inputs[record[path_name]] = record[sha_name]
    # Both initial audits and --reuse bind the same complete unit dependencies.
    # Otherwise a changed world or unit protocol could be sealed alongside an
    # unchanged raw trace after a cache hit without receiving another audit.
    if kind == 'runtime':
        for mode, seed in complete.ROLES:
            inputs.update(pinned_inputs(evidence_dependencies(folder/f'{mode}-{seed}')))
    else:
        scenes = set()
        for record in records:
            unit = (ROOT/record['raw_path']).parent
            inputs.update(pinned_inputs(evidence_dependencies(unit)))
            case = read(unit/'case.json')
            if case.get('scene_calibration'):
                scenes.add(Path(case['scene_calibration']))
        for scene in scenes:
            inputs.update(pinned_inputs(evidence_dependencies(scene)))
    cache = folder/'overall-independent-verification.json'
    if reuse and cache.exists():
        cached = read(cache)
        assert cached['passed'] and cached['input_hashes'] == inputs
        return cached
    if kind == 'runtime':
        regenerated = []
        for mode, seed in complete.ROLES:
            unit = folder/f'{mode}-{seed}'
            p = read(unit/'protocol.json')
            assert p['cases'] == protocol['cases'] and p['mode'] == mode and p['slots_per_case'] == 120
            if mode == 'ppo':
                assert p['policy_sha256'] == protocol['policies'][f'ppo-{seed}']['sha256'] and p['real_policy_process']
            runtime.verify_profile(unit)
            regenerated.extend(complete._runtime_records(unit, protocol['cases'], mode, seed))
        regenerated.sort(key=lambda r: (r['case']['id'], r['mode'], r['seed']))
        assert len(records) == len(regenerated)
        for actual, expected in zip(records, regenerated):
            equal(actual, expected, 'actual runtime normalized metric')
            runtime_physics(actual)
    else:
        for index, record in enumerate(records):
            unit = (ROOT/record['raw_path']).parent
            verification = verify_native.verify(unit)
            assert verification['verified'] and verification['scene_calibration']['verified']
            equal(read(ROOT/record['verification_path']), verification, 'native independent recorded-pose proof')
            for key in ('ticks', 'rmse_m', 'heading_rms', 'rate_rms', 'commanded_rate_rms', 'progress_m', 'failed',
                    'collisions', 'corridor_failures', 'owner_response_misses', 'scheduled_response_misses', 'owner_max_ms',
                    'raw_physics_steps', 'initial_state_fidelity', 'scene_calibration'):
                equal(record[key], verification[key], 'native normalized metric')
            native_summary = read(unit/'summary.json')
            assert all(native_summary['case'][key] == value for key, value in record['case'].items())
            assert native_summary['case']['mode'] == record['mode']
            if record['mode'] == 'ppo':
                assert verification['policy_sha256'] == protocol['policies'][f'ppo-{record["seed"]}']['sha256']
            rows = [json.loads(line) for line in (unit/'ticks.jsonl').open()]
            assert record['policy_worker_failures'] == sum(r['policy_worker_failed'] for r in rows)
            assert record['policy_reply_count'] == sum(r['runtime_reply'] is not None for r in rows)
            assert record['selected_ticks'] == verification['policy_selected_ticks']
            if (index+1) % 12 == 0:
                print('V13 INDEPENDENT NATIVE AUDIT', index+1, '/120', flush=True)
    measured_statistics(records, protocol, assessment)
    check_inputs(inputs)
    result = dict(passed=True, episodes=len(records), owner_slots=sum(r['ticks'] for r in records),
        physical_steps=sum(r['raw_physics_steps'] for r in records), input_hashes=inputs,
        verifier_sha256=digest(__file__), mean_target_qualified=assessment['mean_target_qualified'],
        inferential_target_qualified=assessment['inferential_target_qualified'], failures=assessment['failures'],
        scope='Actual recorded timing/actions and independent physical/statistical replay; observed timing is not WCET. Native is the declared24-case subset.')
    write(cache, result)
    return result


def focused_tests(path, minimum):
    require([path])
    content = path.read_text()
    counts = re.findall(r'\b(\d+) passed\b', content)
    assert counts and int(counts[-1]) >= minimum, ('Missing/insufficient final test summary', path, minimum)
    assert not re.search(r'\b[1-9]\d* (?:failed|errors?)\b', content), 'Final test log contains failures/errors'
    target = DATA/'execution-logs'/path.name
    target.parent.mkdir(exist_ok=True)
    if target.exists() and digest(target) != digest(path):
        target = target.with_name(target.stem+'-'+digest(path)[:12]+target.suffix)
    if target.resolve() != path.resolve():
        shutil.copyfile(path, target)
    return dict(passed=True, tests_passed=int(counts[-1]), minimum=minimum,
        input_hashes={str(target.relative_to(ROOT)): digest(target)})


def audit_stage(name, operation):
    field, expected = STAGES[name]
    try:
        result = operation()
        assert result[field] == expected, (name, 'Unexpected completed stage count', result.get(field), expected)
        return dict(status='VERIFIED', expected=expected, **result)
    except FileNotFoundError as error:
        return dict(status='MISSING', expected=expected, error=str(error))
    except IncompleteEvidence as error:
        return dict(status='INCOMPLETE', expected=expected, error=str(error))
    except (AssertionError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        return dict(status='FAILED', expected=expected, error=f'{type(error).__name__}: {error}')


def verify(*, reuse=False, full_training=False, test_log=None, minimum_tests=100, workers=3):
    from .verify_evaluation import verify_cohort
    from .verify_training import audit_dataset
    assert type(workers) is int and 1 <= workers <= 3, 'Choose1..3 independent audit workers'
    operations = dict(safety=safety, teacher=lambda: teacher(reuse), dataset=audit_dataset,
        training=lambda: training(reuse, full_training, workers), validation=lambda: verify_cohort('validation', reuse, workers),
        final=lambda: verify_cohort('final', reuse, workers), runtime=lambda: measured('runtime', reuse), native=lambda: measured('native', reuse))
    stages = {}
    for name, operation in operations.items():
        stages[name] = audit_stage(name, operation)
        print('V13 AUDIT STAGE', name, stages[name]['status'], flush=True)
    checks = {}
    inputs = {}
    try:
        from .verify_calibration import verify as verify_calibration
        calibration = verify_calibration(DATA/'native-actuator-calibration-v3')
        assert calibration['verified'] and calibration['conditions'] == 8 and calibration['all_initial_speeds_settled']
        checks['actuator_calibration'] = dict(status='VERIFIED', result=calibration)
        calibration_files = [p for p in (DATA/'native-actuator-calibration-v3').rglob('*')
            if p.is_file() and not p.is_symlink() and p.suffix not in ('.pyc', '.pyo', '.nbc', '.nbi') and '__pycache__' not in p.parts]
        inputs.update(pinned_inputs(calibration_files))
    except (AssertionError, KeyError, ValueError, FileNotFoundError) as error:
        checks['actuator_calibration'] = dict(status='FAILED', error=str(error))
    try:
        tests = focused_tests(test_log or Path('/workspace/cloud-setup/ppo-complete-v13-final-tests.log'), minimum_tests)
        inputs.update(tests['input_hashes'])
        checks['focused_tests'] = dict(status='VERIFIED', **tests)
    except (AssertionError, FileNotFoundError) as error:
        checks['focused_tests'] = dict(status='FAILED', error=str(error))
    for stage in stages.values():
        inputs.update(stage.get('input_hashes', {}))
    # Dataset audit returns its own verified digest, not a nested input map.
    if stages['dataset']['status'] == 'VERIFIED':
        inputs.update(pinned_inputs(evidence_dependencies(DATA/'dataset')))
    mean = inferential = False
    try:
        path = DATA/'completion/qualification.json'
        qualification = read(path)
        assert all(stages[name]['status'] == 'VERIFIED' for name in ('validation', 'final', 'runtime', 'native'))
        mean = all(stages[name]['numerical_qualification_passed'] for name in ('validation', 'final')) and all(stages[name]['mean_target_qualified'] for name in ('runtime', 'native'))
        inferential = all(stages[name]['inferential_at_least_10_passed'] for name in ('validation', 'final')) and all(stages[name]['inferential_target_qualified'] for name in ('runtime', 'native'))
        assert qualification['overall_mean_target_qualified'] == mean
        assert qualification['overall_inferential_at_least_10_qualified'] == qualification['overall_qualified'] == inferential
        check_inputs(qualification['input_hashes'])
        for name, expected in qualification['campaign_hashes'].items():
            assert digest(DATA/'completion'/name) == expected
        inputs[str(path.relative_to(ROOT))] = digest(path)
        checks['completion_qualification_record'] = dict(status='VERIFIED')
    except (AssertionError, KeyError, FileNotFoundError) as error:
        mean = inferential = False
        checks['completion_qualification_record'] = dict(status='MISSING_OR_INVALID', error=str(error))
    all_verified = all(s['status'] == 'VERIFIED' for s in stages.values()) and all(s['status'] == 'VERIFIED' for s in checks.values())
    check_inputs(inputs)
    own_sources = sorted([*Path(__file__).parent.glob('*.py'), *Path(__file__).parent.glob('*.md'), *Path(__file__).parent.joinpath('native_assets').glob('*.py')])
    inputs.update(pinned_inputs(own_sources))
    report = dict(passed=all_verified, stages=stages, required_checks=checks,
        all_requested_stages_verified=all_verified, all_training_controller_queries_replayed=bool(full_training and stages['training']['status'] == 'VERIFIED'),
        overall_mean_target_qualified=bool(all_verified and mean), overall_inferential_at_least_10_qualified=bool(all_verified and inferential),
        overall_qualified=bool(all_verified and inferential), input_hashes=inputs, verifier_sha256=digest(__file__),
        limitation='Numerical audit success is distinct from10% performance/safety/quality/runtime qualification. Native transfer covers24prespecified fixtures, not all144final fixtures; host timing is observed, not WCET.')
    write(DATA/'verification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--full-training-controllers', action='store_true')
    parser.add_argument('--test-log', type=Path)
    parser.add_argument('--minimum-tests', type=int, default=100)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    assert args.minimum_tests > 0
    report = verify(reuse=args.reuse, full_training=args.full_training_controllers, test_log=args.test_log,
        minimum_tests=args.minimum_tests, workers=args.workers)
    print(json.dumps(dict(passed=report['passed'], all_requested_stages_verified=report['all_requested_stages_verified'],
        overall_qualified=report['overall_qualified'], stages={name: row['status'] for name, row in report['stages'].items()}), indent=2), flush=True)
    if not report['all_requested_stages_verified']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
