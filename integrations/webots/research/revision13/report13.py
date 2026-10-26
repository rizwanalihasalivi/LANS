"""Verify complete revision13 evidence before applying frozen spending rules.

Confirmation never selects a controller. Development selects only a nonlearned
candidate. Reserved evidence can confirm that choice, never select another one.
"""
import argparse
import csv
import itertools
import json
import math
import re
from functools import lru_cache
from pathlib import Path, PurePosixPath
from statistics import mean

from common13 import P, methods, method_spec, noise_id, road_spec, roads, sha, sources

INTS = ('repetition', 'seed', 'noise_id', 'speed', 'sign', 'steps', 'scheduled_steps', 'submissions')
FLOATS = (
    'lateral_sq_sum', 'heading_sq_sum', 'command_sq_sum', 'actuator_rate_sq_sum',
    'yaw_error_sq_sum', 'actuator_total_variation', 'rmse', 'penalized_rmse',
    'heading_rmse', 'penalized_heading_rmse', 'command_rms', 'actuator_rate_rms',
    'yaw_error_rms', 'active_fraction', 'mean_weight', 'max_rate', 'max_command',
    'max_actuator', 'max_abs_heading', 'max_abs_error', 'wall_p99_s', 'max_packet_age_s')
COLUMNS = set(INTS + FLOATS + (
    'phase', 'road', 'geometry', 'scenario', 'method', 'survived', 'trajectory_sha256'))
PHYSICAL_FIELDS = (
    'steps', 'scheduled_steps', 'survived', 'lateral_sq_sum', 'heading_sq_sum',
    'command_sq_sum', 'actuator_rate_sq_sum', 'yaw_error_sq_sum',
    'actuator_total_variation', 'rmse', 'penalized_rmse', 'heading_rmse',
    'penalized_heading_rmse', 'command_rms', 'actuator_rate_rms', 'yaw_error_rms',
    'max_rate', 'max_command', 'max_actuator', 'max_abs_heading', 'max_abs_error')
METRICS = ('penalized_rmse', 'penalized_heading_rmse', 'command_rms',
           'actuator_rate_rms', 'actuator_total_variation', 'yaw_error_rms')
CANDIDATE_CHECKS = {
    'overall_lateral_gain', 'retain_lateral_gain', 'all_three_pair_means_better',
    'each_geometry_orientation_better', 'nominal_tracking_preserved',
    'active_region_tracking_preserved', 'overall_heading_preserved',
    'active_region_heading_preserved', 'overall_motion_preserved',
    'active_region_motion_preserved', 'rate_and_tv_reduced_vs_lateral',
    'cellwise_survival_preserved', 'exact_severe_fallback'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b, tolerance=1e-10):
    return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def cell(row):
    return row['repetition'], row['speed'], row['road'], row['scenario']


def native_candidate(method):
    if method is None:
        return None
    _, variant, proposer = method_spec(method)
    require(variant in (2, 3, 4) and proposer in ('fixed_m004', 'fixed_p004'),
            'native candidate must be a balanced fixed correction')
    return dict(variant=variant, residual_rad=-.04 if proposer == 'fixed_m004' else .04)


def validate_selection(selection):
    require(isinstance(selection, dict), 'reserved stage requires development selection')
    require(selection.get('phase') == 'development' and selection.get('protocol') == P,
            'selection phase/protocol mismatch')
    candidate = selection.get('selected_candidate')
    require(candidate in P['selection_candidates'], 'missing eligible development candidate')
    require(selection.get('assessments', {}).get(candidate, {}).get('eligible') is True,
            'selected development candidate was not eligible')
    checks = selection['assessments'][candidate].get('checks', {})
    require(isinstance(checks, dict) and set(checks) == CANDIDATE_CHECKS
            and all(value is True for value in checks.values()), 'selected development checks did not pass')
    require(selection.get('native_candidate') == native_candidate(candidate),
            'selected native candidate mismatch')
    require(re.fullmatch('[0-9a-f]{40}', str(selection.get('source_commit', ''))) is not None,
            'invalid development selection source commit')


def validate_metadata(complete):
    require(complete.get('protocol') == P, 'completion protocol mismatch')
    phase = complete.get('phase')
    require(phase in P['phases'], 'unknown phase')
    require(complete.get('submission_semantics') == 'every-available-worker-v1',
            'submission semantics mismatch')
    require(type(complete.get('training_steps')) is int and complete['training_steps'] == 0,
            'these phases require zero training steps')
    require(complete.get('reserved_opened') is (phase == 'reserved'), 'reserved provenance mismatch')
    require(re.fullmatch('[0-9a-f]{40}', str(complete.get('source_commit', ''))) is not None,
            'invalid source commit')
    students = complete.get('students', {})
    require(isinstance(students, dict) and set(students) == set(map(str, P['student_seeds'])),
            'student artifact grid incomplete')
    for entry in students.values():
        require(isinstance(entry, dict) and set(entry) == {'student.pt', 'normalization.npz', 'complete.json'},
                'student artifact metadata incomplete')
        require(all(re.fullmatch('[0-9a-f]{64}', str(v)) for v in entry.values()), 'bad student digest')
    manifest = complete.get('sources', {})
    require(isinstance(manifest, dict) and set(sources()).issubset(manifest), 'source manifest incomplete')
    for name, digest in manifest.items():
        require(isinstance(name, str), 'invalid source path')
        path = PurePosixPath(name)
        require(not path.is_absolute() and bool(path.parts) and '..' not in path.parts
                and str(path) == name and '\\' not in name, 'unsafe source path')
        require(re.fullmatch('[0-9a-f]{64}', str(digest)) is not None, 'invalid source digest')
    if phase == 'reserved':
        validate_selection(complete.get('selection'))
        require(re.fullmatch('[0-9a-f]{64}', str(complete.get('selection_sha256', ''))) is not None,
                'reserved selection digest missing')
    else:
        require(complete.get('selection') is None and complete.get('selection_sha256') is None,
                'nonreserved phase must not inherit a selection')
    return phase


def verify_archive(run, complete):
    phase = validate_metadata(complete)
    archive = (run / 'source').resolve()
    for name, digest in complete['sources'].items():
        path = (archive / name).resolve()
        require(path.is_relative_to(archive) and path.is_file(), 'missing or unsafe archived source: ' + name)
        require(sha(path) == digest, 'archived source digest mismatch: ' + name)
    require(json.loads((archive / 'revision13/protocol.json').read_text()) == P, 'archived protocol mismatch')
    if phase == 'reserved':
        path = run / 'development-selection.json'
        require(path.is_file() and sha(path) == complete['selection_sha256'], 'reserved selection archive mismatch')
        require(json.loads(path.read_text()) == complete['selection'], 'reserved embedded selection mismatch')


def validate(raw_rows, complete):
    phase = validate_metadata(complete)
    names = methods(phase, complete.get('selection'))
    rows = []
    for raw in raw_rows:
        require(set(raw) == COLUMNS, 'episode schema mismatch')
        row = dict(raw)
        for key in INTS:
            try:
                value = float(raw[key]); integer = int(value)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError('invalid integer ' + key) from exc
            require(math.isfinite(value) and integer == value, 'noninteger ' + key)
            row[key] = integer
        for key in FLOATS:
            try:
                value = float(raw[key])
            except (ValueError, TypeError) as exc:
                raise ValueError('invalid metric ' + key) from exc
            require(math.isfinite(value) and value >= 0, 'nonfinite/negative metric ' + key)
            row[key] = value
        require(str(raw['survived']).lower() in ('true', 'false'), 'invalid survival flag')
        row['survived'] = str(raw['survived']).lower() == 'true'
        require(re.fullmatch('[0-9a-f]{64}', str(row['trajectory_sha256'])) is not None, 'invalid trajectory hash')
        require(row['phase'] == phase, 'row phase mismatch')
        rows.append(row)
    expected = set(itertools.product(P['repetitions'], P['speeds'], roads(phase), P['scenarios'], names))
    keys = [cell(r) + (r['method'],) for r in rows]
    require(len(keys) == len(set(keys)) == len(expected) == complete.get('episodes')
            == P['phases'][phase]['episodes'], 'incomplete or duplicate phase grid')
    require(set(keys) == expected, 'unexpected phase grid cell')
    lookup = dict(zip(keys, rows))
    for row in rows:
        _, length, geometry, sign = road_spec(row['road'])
        n, total = row['steps'], row['scheduled_steps']
        require(row['geometry'] == geometry and row['sign'] == sign, 'road geometry/orientation mismatch')
        require(row['seed'] == P['student_seeds'][row['repetition']], 'student seed mismatch')
        require(row['noise_id'] == noise_id(phase, row['repetition'], row['speed'], row['road'], row['scenario']),
                'noise identity or mirror pairing mismatch')
        require(total == math.ceil((length / row['speed'] + 2) / .01) and 0 < n <= total, 'course horizon mismatch')
        require(not row['survived'] or n == total, 'survival requires complete horizon')
        for metric, sum_key in [('rmse', 'lateral_sq_sum'), ('heading_rmse', 'heading_sq_sum'),
                                ('command_rms', 'command_sq_sum'), ('actuator_rate_rms', 'actuator_rate_sq_sum'),
                                ('yaw_error_rms', 'yaw_error_sq_sum')]:
            require(close(row[metric], math.sqrt(row[sum_key] / n)), 'metric arithmetic mismatch: ' + metric)
        require(close(row['penalized_rmse'], math.sqrt((row['lateral_sq_sum'] + (total-n)*6.25) / total)),
                'lateral failure penalty mismatch')
        require(close(row['penalized_heading_rmse'], math.sqrt((row['heading_sq_sum'] + (total-n)*.36) / total)),
                'heading failure penalty mismatch')
        require(row['max_rate'] <= .3500001 and row['max_command'] <= .5000001 and row['max_actuator'] <= .5000001,
                'physical bound violation')
        for rms, maximum in [('rmse', 'max_abs_error'), ('heading_rmse', 'max_abs_heading'),
                             ('command_rms', 'max_command'), ('actuator_rate_rms', 'max_rate')]:
            require(row[rms] <= row[maximum] + 1e-10, 'RMS exceeds recorded maximum')
        require(not row['survived'] or (row['max_abs_error'] <= 2.5 and row['max_abs_heading'] <= .6),
                'survival conflicts with failure thresholds')
        require(row['survived'] or row['max_abs_error'] > 2.5 or row['max_abs_heading'] > .6,
                'failure has no declared threshold violation')
        require(row['active_fraction'] <= 1 and row['mean_weight'] <= .5*row['active_fraction'] + 1e-12,
                'gate activity/weight bound violation')
        require(abs(row['active_fraction']*n-round(row['active_fraction']*n)) <= 1e-7,
                'activity count inconsistent with steps')
        require(0 <= row['submissions'] <= n, 'invalid submission count')
        require(row['actuator_total_variation'] <= .01*math.sqrt(n*row['actuator_rate_sq_sum']) + 1e-9,
                'actuator variation exceeds rate-energy bound')
        require(row['actuator_total_variation'] + 1e-9 >= .01*math.sqrt(row['actuator_rate_sq_sum']),
                'actuator variation below rate-energy bound')
        if row['method'] == 'lqr':
            require(row['active_fraction'] == row['mean_weight'] == row['submissions'] == row['max_packet_age_s'] == 0,
                    'LQR must not submit learned work or have gate authority')
        if row['scenario'] == 'latency100':
            baseline = lookup[cell(row) + ('lqr',)]
            require(row['trajectory_sha256'] == baseline['trajectory_sha256']
                    and all(row[k] == baseline[k] for k in PHYSICAL_FIELDS)
                    and row['active_fraction'] == row['mean_weight'] == 0,
                    'severe-delay exact physical fallback mismatch')
    mirror_comparisons = 0
    for row in rows:
        if row['sign'] != 1:
            continue
        if row['method'] == 'lqr':
            mirrored_method = 'lqr'
        elif row['method'].endswith('_fixed_p004'):
            mirrored_method = row['method'][:-len('fixed_p004')] + 'fixed_m004'
        elif row['method'].endswith('_fixed_m004'):
            mirrored_method = row['method'][:-len('fixed_m004')] + 'fixed_p004'
        else:
            continue
        other = lookup[(row['repetition'], row['speed'], row['geometry']+'_right', row['scenario'], mirrored_method)]
        require(row['steps'] == other['steps'] and row['survived'] == other['survived'], 'mirror survival/horizon mismatch')
        require(all(close(row[k], other[k], 1e-9) for k in PHYSICAL_FIELDS if k != 'survived'),
                'fixed-sign reflection metric mismatch')
        mirror_comparisons += 1
    order = {name: i for i, name in enumerate(names)}
    rows.sort(key=lambda r: (r['repetition'], r['speed'], roads(phase).index(r['road']),
                             P['scenarios'].index(r['scenario']), order[r['method']]))
    return rows, mirror_comparisons


def gain(value, baseline):
    return 100*(1-value/baseline) if baseline else (0. if value == 0 else None)


class Metrics:
    def __init__(self, rows):
        self.rows = rows
        self.lookup = {cell(r)+(r['method'],): r for r in rows}
        self.by_method = {}
        for row in rows:
            self.by_method.setdefault(row['method'], []).append(row)

    def subset(self, method, **filters):
        return [r for r in self.by_method[method] if all(r[k] == v for k, v in filters.items())]

    @lru_cache(maxsize=None)
    def score(self, method, metric='penalized_rmse', **filters):
        return mean(r[metric] for r in self.subset(method, **filters))

    def reduction(self, method, reference='lqr', metric='penalized_rmse', **filters):
        return gain(self.score(method, metric, **filters), self.score(reference, metric, **filters))

    def survival(self, method, reference='lqr', **filters):
        return all(not self.lookup[cell(r)+(reference,)]['survived'] or r['survived']
                   for r in self.subset(method, **filters))

    def summary(self, method, **filters):
        values = self.subset(method, **filters)
        return dict(episodes=len(values), survived=sum(r['survived'] for r in values),
                    **{key: self.score(method, key, **filters) for key in METRICS},
                    reduction_vs_lqr_percent=self.reduction(method, **filters))


def candidate_assessment(metrics, candidate, phase):
    rule = P['selection_rules']
    _, _, proposer = method_spec(candidate)
    lateral = 'lateral_' + proposer
    improvement = metrics.reduction(candidate)
    lateral_improvement = metrics.reduction(lateral)
    score = metrics.score
    active = [r for r in P['scenarios'] if r != 'latency100']
    motion = ('actuator_rate_rms', 'actuator_total_variation')
    checks = {
        'overall_lateral_gain': improvement is not None and improvement >= rule['overall_lateral_gain_vs_lqr_percent'],
        'retain_lateral_gain': improvement is not None and lateral_improvement is not None
            and improvement >= rule['retain_fraction_of_same_sign_lateral_gain']*lateral_improvement,
        'all_three_pair_means_better': all(score(candidate, repetition=i) < score('lqr', repetition=i) for i in P['repetitions']),
        'each_geometry_orientation_better': all(score(candidate, road=r) < score('lqr', road=r) for r in roads(phase)),
        'nominal_tracking_preserved': score(candidate, scenario='nominal') <= score('lqr', scenario='nominal'),
        'active_region_tracking_preserved': all(score(candidate, scenario=r) <= rule['max_active_region_lateral_ratio_lqr']*score('lqr', scenario=r) for r in active),
        'overall_heading_preserved': score(candidate, 'penalized_heading_rmse') <= rule['max_overall_heading_ratio_lqr']*score('lqr', 'penalized_heading_rmse'),
        'active_region_heading_preserved': all(score(candidate, 'penalized_heading_rmse', scenario=r) <= rule['max_active_region_heading_ratio_lqr']*score('lqr', 'penalized_heading_rmse', scenario=r) for r in active),
        'overall_motion_preserved': all(score(candidate, key) <= rule['max_overall_actuator_rate_and_tv_ratio_lqr']*score('lqr', key) for key in motion),
        'active_region_motion_preserved': all(score(candidate, key, scenario=r) <= rule['max_active_region_actuator_rate_and_tv_ratio_lqr']*score('lqr', key, scenario=r) for r in active for key in motion),
        'rate_and_tv_reduced_vs_lateral': all(metrics.reduction(candidate, lateral, key) is not None and metrics.reduction(candidate, lateral, key) >= rule['minimum_rate_and_tv_reduction_vs_same_sign_lateral_percent'] for key in motion),
        'cellwise_survival_preserved': metrics.survival(candidate),
        'exact_severe_fallback': True,
    }
    return dict(eligible=all(checks.values()), checks=checks, mean_penalized_rmse=score(candidate),
                reduction_vs_lqr_percent=improvement, same_sign_lateral_gain_percent=lateral_improvement,
                rate_reduction_vs_same_sign_lateral_percent=metrics.reduction(candidate, lateral, 'actuator_rate_rms'),
                tv_reduction_vs_same_sign_lateral_percent=metrics.reduction(candidate, lateral, 'actuator_total_variation'))


def assess(raw_rows, complete):
    rows, mirrors = validate(raw_rows, complete)
    phase = complete['phase']
    names = methods(phase, complete.get('selection'))
    m = Metrics(rows)
    result = dict(phase=phase, protocol=P, source_commit=complete['source_commit'],
                  summary={name: m.summary(name) for name in names},
                  regions={region: {name: m.summary(name, scenario=region) for name in names} for region in P['scenarios']},
                  pairs={str(i): {name: m.summary(name, repetition=i) for name in names} for i in P['repetitions']},
                  geometry_orientation={road: {name: m.summary(name, road=road) for name in names} for road in roads(phase)},
                  mirror_comparisons=mirrors, mirror_tolerance=1e-9, training_steps=0,
                  reserved_opened=phase == 'reserved', selected_candidate=None, native_candidate=None)
    if phase == 'confirmation':
        subsets = {
            'original_positive': lambda r: r['geometry'] in ('sine120', 'dlc220') and r['sign'] == 1,
            'original_mirrored': lambda r: r['geometry'] in ('sine120', 'dlc220') and r['sign'] == -1,
            'new_positive': lambda r: r['geometry'] not in ('sine120', 'dlc220') and r['sign'] == 1,
            'new_mirrored': lambda r: r['geometry'] not in ('sine120', 'dlc220') and r['sign'] == -1,
        }
        result['replication_subsets'] = {label: {name: Metrics([r for r in rows if predicate(r)]).summary(name) for name in names}
                                         for label, predicate in subsets.items()}
        reference = Metrics([r for r in rows if subsets['original_positive'](r)])
        candidate = 'lateral_fixed_p004'
        delta = reference.reduction(candidate)
        checks = dict(at_least_five_percent=delta is not None and delta >= 5.,
                      all_three_pair_means_lower=all(reference.score(candidate, repetition=i) < reference.score('lqr', repetition=i) for i in P['repetitions']),
                      cellwise_survival=reference.survival(candidate), exact_severe_fallback=True)
        result.update(replication_checks=checks, replication_pass=all(checks.values()),
                      next_action='predeclared_development_without_revising_criteria')
    elif phase == 'development':
        assessments = {name: candidate_assessment(m, name, phase) for name in P['selection_candidates']}
        eligible = [name for name, value in assessments.items() if value['eligible']]
        selected = None
        if eligible:
            minimum = min(assessments[name]['mean_penalized_rmse'] for name in eligible)
            close_candidates = [name for name in eligible if assessments[name]['mean_penalized_rmse'] <= minimum*1.001]
            selected = min(close_candidates, key=lambda name: (method_spec(name)[1], method_spec(name)[2] != 'fixed_p004'))
        result.update(assessments=assessments, eligible_candidates=eligible, selected_candidate=selected,
                      native_candidate=native_candidate(selected),
                      next_action='freeze_selection_then_reserved_confirmation' if selected else 'stop_reserved_native_and_learning')
    else:
        selected = complete['selection']['selected_candidate']
        assessment = candidate_assessment(m, selected, phase)
        result.update(selected_candidate=selected, native_candidate=native_candidate(selected),
                      assessments={selected: assessment}, confirmed=assessment['eligible'],
                      selection_sha256=complete['selection_sha256'],
                      next_action='frozen_nonlearned_native_confirmation' if assessment['eligible'] else 'stop_native_and_learning_no_reselection')
    return rows, result


def table(lines, title, summary):
    lines += ['', '## ' + title, '', '| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for name, value in summary.items():
        delta = value['reduction_vs_lqr_percent']
        percent = 'undefined' if delta is None else f'{delta:+.3f}%'
        lines.append(f"| {name} | {value['survived']}/{value['episodes']} | {value['penalized_rmse']:.8f} | {value['penalized_heading_rmse']:.8f} | {value['actuator_rate_rms']:.8f} | {value['actuator_total_variation']:.8f} | {percent} |")


def write_report(run):
    run = Path(run)
    complete = json.loads((run / 'complete.json').read_text())
    verify_archive(run, complete)
    with (run / 'episodes.csv').open(newline='') as handle:
        rows, result = assess(list(csv.DictReader(handle)), complete)
    phase = result['phase']
    lines = ['# Revision13 ' + phase + ' results', '',
             f"Executable freeze: `{result['source_commit']}`. Verified {len(rows)} complete-grid episode records, archived source hashes, metric arithmetic, physical bounds and severe-delay fallback. Additional training steps: 0.", '',
             'Each method has 432 paired cells. Mirrored orientations share transformed noise and initial errors; they are correlated symmetry checks, not additional independent seeds. Means give equal weight to episodes.']
    table(lines, 'Overall metrics', result['summary'])
    if phase == 'confirmation':
        for label, summary in result['replication_subsets'].items():
            table(lines, 'Replication subset: ' + label, summary)
        lines += ['', f"Exact-match original-positive replication screen: **{result['replication_pass']}**.",
                  'This screen concerns the fixed +0.04 correction and the original positive-orientation roads. The full eight-road mean is a different distribution from the earlier 9.122% figure. Confirmation does not select a controller.']
    else:
        lines += ['', '## Frozen candidate checks', '', '| Candidate | Pass | Failed checks |', '|---|---|---|']
        for name, value in result['assessments'].items():
            failed = ', '.join(key for key, passed in value['checks'].items() if not passed) or 'none'
            lines.append(f"| {name} | {value['eligible']} | {failed} |")
        lines += ['', f"Selected candidate: **{result['selected_candidate'] or 'none'}**.",
                  f"Next action: `{result['next_action']}`."]
        if phase == 'reserved':
            lines += ['', f"Reserved confirmation: **{result['confirmed']}**. No reselection is permitted."]
    for region, summary in result['regions'].items():
        table(lines, 'Region: ' + region, summary)
    lines += ['', '## Interpretation limits', '',
              'Heading and lateral tables use declared failure penalties; command, actuator-rate, total-variation and yaw metrics describe executed steps. Failed cases remain in denominators and survival is a separate required check. Full metric sums are stored for every episode; representative traces do not constitute complete telemetry for every case.',
              f"Fixed-sign reflection integrity passed {result['mirror_comparisons']} paired comparisons at 1e-9 numerical tolerance. Opposite fixed signs should tie globally on the balanced mirror grid; that tie is not evidence of learning. The student need not be reflection-equivariant.",
              'Frozen students retain their original weights and normalization. Student rows are comparators; this stage selects only a nonlearned balanced controller. Engineering heading/smoothness budgets are not certified comfort or safety limits. Three noise/model pairs and analytic road variations do not establish broad statistical superiority or physical deployment safety.',
              'Reserved roads include sine180/DLC286 excluded from gate development; original-road confirmation and new-shape results should be distinguished. A native run, teacher diagnostic or PPO pilot is conditional on its preceding frozen checks, never automatic from a favorable mean. No training or native action is launched by this reporter.']
    (run / 'report.md').write_text('\n'.join(lines) + '\n')
    (run / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    verification = dict(verified=True, phase=phase, protocol=P, episodes=len(rows), unique_paired_grid=True,
                        source_commit=complete['source_commit'], archived_source_hashes=True,
                        metric_arithmetic=True, physical_bounds=True, severe_exact_fallback=True,
                        mirror_comparisons=result['mirror_comparisons'], mirror_tolerance=1e-9,
                        training_steps=0, reserved_opened=phase == 'reserved',
                        selected_candidate=result['selected_candidate'], native_candidate=result['native_candidate'])
    if phase == 'development':
        (run / 'selection.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    if phase == 'reserved':
        verification['confirmed'] = result['confirmed']
        verification['selection_sha256'] = complete['selection_sha256']
    if phase == 'confirmation':
        verification['replication_pass'] = result['replication_pass']
    (run / 'verification.json').write_text(json.dumps(verification, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    result = write_report(args.run)
    print(json.dumps({key: result[key] for key in ('phase', 'selected_candidate', 'next_action')}, indent=2))
