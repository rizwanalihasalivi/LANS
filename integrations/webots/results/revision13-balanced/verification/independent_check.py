#!/usr/bin/env python3
"""Independent stdlib-only audit of frozen R13 results; never runs a plant/model.

Reads CSV/JSON/gzip data and git objects. Writes only the requested /tmp report.
TV is reconstructed from increments for saved traces; the remaining episodes
support TV/rate-energy bounds, not an independent raw-increment reconstruction.
"""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import struct
import subprocess

FREEZE = '583ee07e1ec8f8ce61eb457796e301f8dd9750ac'
TEXT = {'phase', 'road', 'geometry', 'scenario', 'method', 'trajectory_sha256'}
INTEGER = {'repetition', 'seed', 'noise_id', 'speed', 'sign', 'steps', 'scheduled_steps', 'submissions'}
MEASURES = ['penalized_rmse', 'penalized_heading_rmse', 'command_rms',
            'actuator_rate_rms', 'actuator_total_variation', 'yaw_error_rms']
SQUARES = {'rmse': 'lateral_sq_sum', 'heading_rmse': 'heading_sq_sum',
           'command_rms': 'command_sq_sum', 'actuator_rate_rms': 'actuator_rate_sq_sum',
           'yaw_error_rms': 'yaw_error_sq_sum'}
PHYSICAL = list(SQUARES) + list(SQUARES.values()) + [
    'steps', 'scheduled_steps', 'survived', 'penalized_rmse', 'penalized_heading_rmse',
    'actuator_total_variation', 'max_rate', 'max_command', 'max_actuator', 'max_abs_heading', 'max_abs_error']


def ensure(ok, message):
    if not ok:
        raise AssertionError(message)


def near(a, b, label, tolerance=1e-10):
    ensure(math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance), f'{label}: {a} != {b}')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_csv(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def read_rows(path):
    output = []
    for record in raw_csv(path):
        row = {}
        for key, value in record.items():
            if key in TEXT:
                row[key] = value
            elif key == 'survived':
                ensure(value in ('True', 'False'), 'invalid survival')
                row[key] = value == 'True'
            else:
                number = float(value)
                ensure(math.isfinite(number), f'nonfinite {key}')
                if key in INTEGER:
                    ensure(number == int(number), f'noninteger {key}')
                    number = int(number)
                elif key not in TEXT:
                    ensure(number >= 0, f'negative {key}')
                row[key] = number
        output.append(row)
    return output


def key(row):
    return tuple(row[k] for k in ('repetition', 'speed', 'road', 'scenario', 'method'))


def average(values):
    values = list(values)
    ensure(bool(values), 'empty aggregation')
    return math.fsum(values) / len(values)


def path_reference(x, config, sign):
    kind, amplitude, wavelength, phase, scale = config['parameters']
    x /= scale
    if kind == 0:
        angular = 2 * math.pi / wavelength
        s, c = math.sin(angular*x+phase), math.cos(angular*x+phase)
        y, first, second = amplitude*s, amplitude*angular*c, -amplitude*angular**2*s
    elif x < 15 or x >= 165:
        y, first, second = 0., 0., 0.
    elif 75 <= x < 105:
        y, first, second = 3.5, 0., 0.
    else:
        rising = x < 75
        u = (x-(15 if rising else 105))/60
        smooth = 10*u**3-15*u**4+6*u**5
        direction = 1 if rising else -1
        y = 3.5*(smooth if rising else 1-smooth)
        first = direction*3.5*(30*u**2-60*u**3+30*u**4)/60
        second = direction*3.5*(60*u-180*u**2+120*u**3)/3600
    y *= sign
    first *= sign/scale
    second *= sign/scale**2
    return y, math.atan(first), second/(1+first**2)**1.5


def verify_trace(path, row, protocol):
    with gzip.open(path, 'rt', newline='') as handle:
        records = list(csv.DictReader(handle))
    ensure(len(records) == row['steps'], 'trace count '+str(path))
    quantities = {name: [] for name in SQUARES.values()}
    variations, weights = [], []
    old = 0.
    trajectory = hashlib.sha256()
    submissions = 0
    for i, raw in enumerate(records):
        trace = {k: (v if k == 'submitted' else float(v)) for k, v in raw.items() if v != ''}
        ensure(trace['tick'] == i, 'trace tick mismatch')
        near(trace['state_time_s'], (i+1)*.01, 'trace timestamp')
        y, heading, curvature = path_reference(trace['x'], protocol['geometry'][row['geometry']], row['sign'])
        for actual, wanted, label in ((trace['reference'], y, 'reference'),
                (trace['reference_heading'], heading, 'reference heading'),
                (trace['error'], trace['y']-y, 'lateral error'),
                (trace['heading_error'], trace['heading']-heading, 'heading error'),
                (trace['actuator_rate'], (trace['actuator']-old)/.01, 'actual actuator rate')):
            near(actual, wanted, label, 1e-9)
        quantities['lateral_sq_sum'].append(trace['error']**2)
        quantities['heading_sq_sum'].append(trace['heading_error']**2)
        quantities['command_sq_sum'].append(trace['command']**2)
        quantities['actuator_rate_sq_sum'].append(((trace['actuator']-old)/.01)**2)
        quantities['yaw_error_sq_sum'].append((trace['yaw_rate']-row['speed']*curvature)**2)
        variations.append(abs(trace['actuator']-old))
        old = trace['actuator']
        weights.append(trace['weight'])
        submissions += trace['submitted'] == 'True'
        ensure(abs(trace['command']) <= .5000001 and abs(old) <= .5000001
               and abs(trace['actuator_rate']) <= .3500001, 'trace physical bounds')
        if trace['weight'] == 0 or row['scenario'] == 'latency100':
            ensure(trace['command'] == trace['baseline'], 'trace fallback command')
        if row['scenario'] == 'latency100':
            ensure(trace['weight'] == 0, 'trace severe authority')
        trajectory.update(struct.pack('<7d', *[trace[k] for k in
            ('command', 'x', 'y', 'heading', 'vy', 'yaw_rate', 'actuator')]))
    for name, values in quantities.items():
        near(row[name], math.fsum(values), 'trace '+name, 1e-9)
    near(row['actuator_total_variation'], math.fsum(variations), 'trace TV')
    near(row['mean_weight'], average(weights), 'trace mean weight')
    near(row['active_fraction'], sum(w > 0 for w in weights)/len(weights), 'trace activity')
    ensure(row['submissions'] == submissions, 'trace submissions')
    ensure(row['trajectory_sha256'] == trajectory.hexdigest(), 'trace physical SHA256')
    return len(records)


def audit(run, repo, protocol):
    complete = json.loads((run/'complete.json').read_text())
    phase = complete['phase']
    ensure(phase in ('confirmation', 'development'), 'unexpected audit phase')
    ensure(complete['source_commit'] == FREEZE and complete['protocol'] == protocol, 'freeze/protocol drift')
    ensure(complete['training_steps'] == 0 and complete['reserved_opened'] is False, 'closed-stage violation')
    ensure(complete['selection'] is None and complete['selection_sha256'] is None, 'unexpected selection')
    ensure(complete['submission_semantics'] == 'every-available-worker-v1', 'worker cadence changed')
    for name, wanted in complete['sources'].items():
        ensure(digest(run/'source'/name) == wanted, 'source archive changed: '+name)
        frozen = subprocess.check_output(['git', 'show', FREEZE+':integrations/webots/research/'+name], cwd=repo)
        ensure(hashlib.sha256(frozen).hexdigest() == wanted, 'source differs from freeze: '+name)
    for seed, files in complete['students'].items():
        for name, wanted in files.items():
            relative = f'integrations/webots/results/revision8-student/students/{seed}/{name}'
            ensure(digest(repo/relative) == wanted, 'student changed: '+relative)
            frozen = subprocess.check_output(['git', 'show', FREEZE+':'+relative], cwd=repo)
            ensure(hashlib.sha256(frozen).hexdigest() == wanted, 'student differs from freeze: '+relative)
    ensure(set(complete['students']) == set(map(str, protocol['student_seeds'])), 'student grid')
    merged = []
    for rep in protocol['repetitions']:
        shard = run/f'pair-{rep}'
        metadata = json.loads((shard/'complete.json').read_text())
        records = raw_csv(shard/'episodes.csv')
        ensure(metadata == dict(episodes=len(records), repetition=rep, phase=phase), 'shard metadata')
        merged.extend(records)
    ensure(merged == raw_csv(run/'episodes.csv'), 'parent CSV differs from complete shard concatenation')
    rows = read_rows(run/'episodes.csv')
    geometries = protocol['development_geometries']
    roads = [base+'_'+side for base in geometries for side in ('left', 'right')]
    methods = protocol['phases'][phase]['methods']
    expected = set(itertools.product(protocol['repetitions'], protocol['speeds'], roads, protocol['scenarios'], methods))
    lookup = {key(row): row for row in rows}
    ensure(len(rows) == len(lookup) == len(expected) == complete['episodes']
           == protocol['phases'][phase]['episodes'] and set(lookup) == expected, 'incomplete/duplicate grid')
    severe, mirror, trace_count, trace_ticks = 0, 0, 0, 0
    maximum_mirror_absolute_difference = 0.
    expected_traces = set()
    for row in rows:
        base, side = row['road'].rsplit('_', 1)
        sign = 1 if side == 'left' else -1
        ensure(row['geometry'] == base and row['sign'] == sign and row['phase'] == phase, 'geometry identity')
        ensure(row['seed'] == protocol['student_seeds'][row['repetition']], 'model seed identity')
        noise = (protocol['phases'][phase]['noise_base']+row['repetition']*100000+row['speed']*1000
                 +list(protocol['geometry']).index(base)*100+protocol['scenarios'].index(row['scenario']))
        ensure(row['noise_id'] == noise, 'noise seed identity')
        n, total = row['steps'], math.ceil((protocol['geometry'][base]['length_m']/row['speed']+2)/.01)
        ensure(row['scheduled_steps'] == total and 0 < n <= total, 'road horizon')
        ensure(not row['survived'] or n == total, 'short surviving episode')
        for metric, sum_name in SQUARES.items():
            near(row[metric], math.sqrt(row[sum_name]/n), 'episode '+metric)
        near(row['penalized_rmse'], math.sqrt((row['lateral_sq_sum']+(total-n)*2.5**2)/total), 'penalized lateral')
        near(row['penalized_heading_rmse'], math.sqrt((row['heading_sq_sum']+(total-n)*.6**2)/total), 'penalized heading')
        rate_energy = row['actuator_rate_sq_sum']
        ensure(.01*math.sqrt(rate_energy)-1e-9 <= row['actuator_total_variation']
               <= .01*math.sqrt(n*rate_energy)+1e-9, 'TV inconsistent with rate energy')
        ensure(row['max_rate'] <= .3500001 and row['max_command'] <= .5000001
               and row['max_actuator'] <= .5000001, 'episode physical bounds')
        crossed = row['max_abs_error'] > 2.5 or row['max_abs_heading'] > .6
        ensure(row['survived'] != crossed, 'survival threshold mismatch')
        ensure(0 <= row['active_fraction'] <= 1 and 0 <= row['mean_weight'] <= .5*row['active_fraction']+1e-12, 'authority')
        if row['scenario'] == 'latency100':
            lqr = lookup[key(row)[:-1]+('lqr',)]
            ensure(all(row[k] == lqr[k] for k in PHYSICAL)
                   and row['trajectory_sha256'] == lqr['trajectory_sha256']
                   and row['mean_weight'] == row['active_fraction'] == 0, 'severe fallback equality')
            severe += row['method'] != 'lqr'
        method = row['method']
        if sign == 1 and (method == 'lqr' or '_fixed_' in method):
            other_method = method.replace('_p004', '_swap').replace('_m004', '_p004').replace('_swap', '_m004')
            other = lookup[(row['repetition'], row['speed'], base+'_right', row['scenario'], other_method)]
            ensure(row['survived'] == other['survived'] and row['steps'] == other['steps'], 'mirror survival')
            for field in PHYSICAL:
                near(row[field], other[field], 'mirror '+field, 1e-9)
                maximum_mirror_absolute_difference = max(maximum_mirror_absolute_difference, abs(row[field]-other[field]))
            ensure(row['noise_id'] == other['noise_id'], 'mirror canonical noise')
            mirror += 1
        if row['repetition'] == 0 and row['speed'] == 25 and row['scenario'] in ('nominal', 'tire_mismatch', 'latency100'):
            trace = run/'pair-0/traces'/f'{row["road"]}-{row["scenario"]}-{method}.csv.gz'
            expected_traces.add(trace)
            trace_ticks += verify_trace(trace, row, protocol)
            trace_count += 1
    actual_traces = set(run.glob('pair-*/traces/*.csv.gz'))
    ensure(actual_traces == expected_traces, 'trace grid differs from declared subset')

    def selected(method, **filters):
        return [r for r in rows if r['method'] == method and all(r[k] == v for k, v in filters.items())]

    def score(method, metric='penalized_rmse', **filters):
        return average(r[metric] for r in selected(method, **filters))

    def gain(method, reference='lqr', metric='penalized_rmse', **filters):
        return 100*(1-score(method, metric, **filters)/score(reference, metric, **filters))

    def summary(method, **filters):
        values = selected(method, **filters)
        return dict(episodes=len(values), survived=sum(r['survived'] for r in values),
                    **{name: score(method, name, **filters) for name in MEASURES},
                    reduction_vs_lqr_percent=gain(method, **filters))

    result = dict(phase=phase, verified=True, episodes=len(rows), survived=sum(r['survived'] for r in rows),
        severe_nonbaseline_pairs=severe, mirror_pairs=mirror, mirror_max_abs_difference=maximum_mirror_absolute_difference,
        traces_recomputed=trace_count, trace_ticks_recomputed=trace_ticks,
        summary={method: summary(method) for method in methods},
        regions={region: {method: summary(method, scenario=region) for method in methods} for region in protocol['scenarios']},
        pairs={str(rep): {method: summary(method, repetition=rep) for method in methods} for rep in protocol['repetitions']},
        geometry_orientation={road: {method: summary(method, road=road) for method in methods} for road in roads})
    if phase == 'development':
        limits = protocol['selection_rules']
        active = [s for s in protocol['scenarios'] if s != 'latency100']
        motion = ('actuator_rate_rms', 'actuator_total_variation')
        assessed = {}
        for candidate in protocol['selection_candidates']:
            same_sign = 'lateral_'+candidate.split('_', 2)[2]
            checks = {
                'overall_lateral_gain': gain(candidate) >= limits['overall_lateral_gain_vs_lqr_percent'],
                'retain_lateral_gain': gain(candidate) >= limits['retain_fraction_of_same_sign_lateral_gain']*gain(same_sign),
                'all_three_pair_means_better': all(score(candidate, repetition=i) < score('lqr', repetition=i) for i in protocol['repetitions']),
                'each_geometry_orientation_better': all(score(candidate, road=road) < score('lqr', road=road) for road in roads),
                'nominal_tracking_preserved': score(candidate, scenario='nominal') <= score('lqr', scenario='nominal'),
                'active_region_tracking_preserved': all(score(candidate, scenario=s) <= limits['max_active_region_lateral_ratio_lqr']*score('lqr', scenario=s) for s in active),
                'overall_heading_preserved': score(candidate, 'penalized_heading_rmse') <= limits['max_overall_heading_ratio_lqr']*score('lqr', 'penalized_heading_rmse'),
                'active_region_heading_preserved': all(score(candidate, 'penalized_heading_rmse', scenario=s) <= limits['max_active_region_heading_ratio_lqr']*score('lqr', 'penalized_heading_rmse', scenario=s) for s in active),
                'overall_motion_preserved': all(score(candidate, metric) <= limits['max_overall_actuator_rate_and_tv_ratio_lqr']*score('lqr', metric) for metric in motion),
                'active_region_motion_preserved': all(score(candidate, metric, scenario=s) <= limits['max_active_region_actuator_rate_and_tv_ratio_lqr']*score('lqr', metric, scenario=s) for metric in motion for s in active),
                'rate_and_tv_reduced_vs_lateral': all(gain(candidate, same_sign, metric) >= limits['minimum_rate_and_tv_reduction_vs_same_sign_lateral_percent'] for metric in motion),
                'cellwise_survival_preserved': all(r['survived'] or not lookup[key(r)[:-1]+('lqr',)]['survived'] for r in selected(candidate)),
                'exact_severe_fallback': all(r['trajectory_sha256'] == lookup[key(r)[:-1]+('lqr',)]['trajectory_sha256'] for r in selected(candidate, scenario='latency100')),
            }
            assessed[candidate] = dict(eligible=all(checks.values()), checks=checks,
                mean_penalized_rmse=score(candidate), reduction_vs_lqr_percent=gain(candidate),
                same_sign_lateral_gain_percent=gain(same_sign),
                rate_reduction_vs_same_sign_lateral_percent=gain(candidate, same_sign, motion[0]),
                tv_reduction_vs_same_sign_lateral_percent=gain(candidate, same_sign, motion[1]))
        eligible = [name for name, info in assessed.items() if info['eligible']]
        winner = None
        if eligible:
            best = min(score(name) for name in eligible)
            tied = [name for name in eligible if score(name) <= best*1.001]
            winner = min(tied, key=lambda name: (protocol['variants'][name.rsplit('_fixed', 1)[0]], not name.endswith('p004')))
        result.update(assessments=assessed, eligible_candidates=eligible, selected_candidate=winner)
    else:
        subset_rows = [r for r in rows if r['geometry'] in ('sine120', 'dlc220') and r['sign'] == 1]
        def original(method, rep=None):
            return [r for r in subset_rows if r['method'] == method and (rep is None or r['repetition'] == rep)]
        candidate = 'lateral_fixed_p004'
        reduction = 100*(1-average(r['penalized_rmse'] for r in original(candidate))/average(r['penalized_rmse'] for r in original('lqr')))
        checks = dict(at_least_five_percent=reduction >= 5,
            all_three_pair_means_lower=all(average(r['penalized_rmse'] for r in original(candidate, rep)) < average(r['penalized_rmse'] for r in original('lqr', rep)) for rep in protocol['repetitions']),
            cellwise_survival=all(r['survived'] or not lookup[key(r)[:-1]+('lqr',)]['survived'] for r in original(candidate)),
            exact_severe_fallback=all(r['trajectory_sha256'] == lookup[key(r)[:-1]+('lqr',)]['trajectory_sha256'] for r in original(candidate) if r['scenario'] == 'latency100'))
        result.update(original_positive_fixed_p_gain_percent=reduction, replication_checks=checks, replication_pass=all(checks.values()))
    if (run/'summary.json').exists():
        reported = json.loads((run/'summary.json').read_text())
        for group in ('summary', 'regions', 'pairs', 'geometry_orientation', 'assessments', 'eligible_candidates', 'selected_candidate', 'replication_checks', 'replication_pass'):
            if group in result:
                compare(result[group], reported[group], group)
        ensure(reported['mirror_comparisons'] == mirror, 'reported mirror count')
        result['independent_report_agreement'] = True
    else:
        result['independent_report_agreement'] = 'report not yet written'
    return result


def compare(actual, reported, label):
    if isinstance(actual, dict):
        ensure(set(actual) == set(reported), label+' keys mismatch')
        for name in actual:
            compare(actual[name], reported[name], label+'/'+name)
    elif isinstance(actual, float):
        near(actual, reported, label, 1e-9)
    else:
        ensure(actual == reported, label+' mismatch')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path('/workspace/LANS-webots'))
    parser.add_argument('--phases', nargs='+', choices=['confirmation', 'development'], default=['confirmation', 'development'])
    parser.add_argument('--output', type=Path, default=Path('/tmp/r13-independent-verification.json'))
    args = parser.parse_args()
    ensure(args.output.resolve().is_relative_to(Path('/tmp')), 'audit output must remain under /tmp')
    frozen = subprocess.check_output(['git', 'show', FREEZE+':integrations/webots/research/revision13/protocol.json'], cwd=args.repo)
    protocol = json.loads(frozen)
    folder = args.repo/'integrations/webots/results/revision13-balanced'
    missing = [phase for phase in args.phases if not (folder/phase/'complete.json').exists()]
    if missing:
        print(json.dumps(dict(ready=True, waiting_for_complete=missing)))
        return 2
    outcome = dict(independent_checker_sha256=digest(Path(__file__)), source_commit=FREEZE,
        protocol_sha256=hashlib.sha256(frozen).hexdigest(),
        implementation='stdlib-only; no imports of project reporter/controller code',
        limitation='All episodes: sums/counts/RMS/TV-energy consistency. Direct TV and physical-state hash reconstruction only for the predeclared saved trace subset.',
        phases={phase: audit(folder/phase, args.repo, protocol) for phase in args.phases})
    args.output.write_text(json.dumps(outcome, indent=2, allow_nan=False)+'\n')
    print(json.dumps({phase: {k: values[k] for k in ('verified', 'episodes', 'survived', 'traces_recomputed', 'severe_nonbaseline_pairs', 'mirror_pairs', 'independent_report_agreement')}
        for phase, values in outcome['phases'].items()}, indent=2))
    print(str(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
