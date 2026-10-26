#!/usr/bin/env python3
"""Posthoc trace diagnostics only; no rollouts, policy loads, tuning or reserved data.

Example:
  python /tmp/lans-v12-tradeoffs.py --repo /workspace/LANS-webots \
      --output /tmp/lans-v12-tradeoffs.json

Only the bodies of reference/path_values from the frozen core.py are evaluated.
This avoids importing training/simulation packages or writing source-tree caches.
"""
import argparse
import ast
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics


FOCUS = ('lqr', 'legacy_student', 'preview_student', 'lateral_student',
         'lateral_fixed_p004', 'lateral_fixed_m004')
METRICS = ('lateral_rmse_m', 'heading_rmse_rad', 'command_rms_rad',
           'actuator_rate_rms_rad_s', 'actuator_total_variation_rad')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_path_function(path):
    tree = ast.parse(path.read_text())
    funcs = []
    for name in ('reference', 'path_values'):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        funcs.append(node)
    module = ast.Module(body=funcs, type_ignores=[])
    namespace = {'math': math}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace['path_values']


def rms(values):
    return math.sqrt(statistics.fmean(v * v for v in values))


def pct(value, baseline):
    return 100 * (value / baseline - 1)


def markdown(result):
    aggregate = result['aggregate_equal_region_mean']['all_six_regions']
    active = result['aggregate_equal_region_mean']['five_active_regions']
    lines = [
        '# Revision 12 posthoc trace tradeoff diagnostic', '',
        'Existing development traces only: repetition 0 / student seed 701, '
        '25 m/s, dlc220, one trajectory per method in each of six regions. '
        'This is not a tradeoff analysis of all 108 paired cells, an independent '
        'replication, a predeclared selection criterion, or a safety proof. '
        'No new rollouts, training, tuning, policy loading or reserved-split access.', '',
        'Heading error is true post-step heading minus the path heading computed '
        'at the same post-step x by the frozen core path_values function. '
        'Command RMS uses each issued command. Actuator rate is '
        '(delta[t]-delta[t-1])/0.01 s, including the known initial delta[-1]=0. '
        'Total variation sums all absolute actuator increments, including the first. '
        'Every trace has 1080 samples (10.8 s) and is complete. '
        'Aggregates below are arithmetic means of episode metrics; relative changes '
        'compare those means to LQR, rather than averaging regional percentages.', '',
        '## Six-region mean episode metrics', '',
        '| Method | Lateral RMSE (m) | Heading RMSE (rad) | Command RMS (rad) | Actuator rate RMS (rad/s) | Actuator TV (rad) |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for method in FOCUS:
        metrics = aggregate[method]['mean_metrics']
        lines.append('| ' + method + ' | ' + ' | '.join(f'{metrics[k]:.6f}' for k in METRICS) + ' |')
    lines += ['', '## Percent change versus LQR (negative is lower)', '',
              '| Method | Lateral RMSE | Heading RMSE | Command RMS | Actuator rate RMS | Actuator TV |',
              '|---|---:|---:|---:|---:|---:|']
    for method in FOCUS[1:]:
        metrics = aggregate[method]['percent_change_vs_lqr']
        lines.append('| ' + method + ' | ' + ' | '.join(f'{metrics[k]:+.3f}%' for k in METRICS) + ' |')
    lines += ['', '## Regional percent change versus LQR', '',
              '| Region | Method | Lateral RMSE | Heading RMSE | Command RMS | Actuator rate RMS | Actuator TV |',
              '|---|---|---:|---:|---:|---:|---:|']
    for region in result['regions']:
        for method in ('legacy_student', 'preview_student', 'lateral_student', 'lateral_fixed_p004', 'lateral_fixed_m004'):
            metrics = result['by_region'][region][method]['percent_change_vs_lqr']
            lines.append('| ' + region + ' | ' + method + ' | ' + ' | '.join(f'{metrics[k]:+.3f}%' for k in METRICS) + ' |')
    positive = aggregate['lateral_fixed_p004']['percent_change_vs_lqr']
    student = aggregate['lateral_student']['percent_change_vs_lqr']
    nominal_student = result['by_region']['nominal']['lateral_student']['percent_change_vs_lqr']
    sensor_student = result['by_region']['sensor_stress']['lateral_student']['percent_change_vs_lqr']
    sensor_preview = result['by_region']['sensor_stress']['preview_student']['percent_change_vs_lqr']
    lines += ['', '## Interpretation', '',
        f"On this representative subset, lateral_fixed_p004 changes lateral RMSE by {positive['lateral_rmse_m']:+.3f}%, "
        f"but heading RMSE by {positive['heading_rmse_rad']:+.3f}%, command RMS by {positive['command_rms_rad']:+.3f}%, "
        f"actuator-rate RMS by {positive['actuator_rate_rms_rad_s']:+.3f}%, and actuator TV by {positive['actuator_total_variation_rad']:+.3f}%.", '',
        f"For lateral_student the corresponding changes are {student['lateral_rmse_m']:+.3f}%, "
        f"{student['heading_rmse_rad']:+.3f}%, {student['command_rms_rad']:+.3f}%, "
        f"{student['actuator_rate_rms_rad_s']:+.3f}%, and {student['actuator_total_variation_rad']:+.3f}%.", '',
        f"The student's largest actuator-motion cost is nominal: rate RMS {nominal_student['actuator_rate_rms_rad_s']:+.3f}% "
        f"and TV {nominal_student['actuator_total_variation_rad']:+.3f}%. In sensor stress, lateral_student has "
        f"rate RMS {sensor_student['actuator_rate_rms_rad_s']:+.3f}% and TV {sensor_student['actuator_total_variation_rad']:+.3f}%. "
        f"There preview_student improves lateral RMSE more ({sensor_preview['lateral_rmse_m']:+.3f}% versus "
        f"{sensor_student['lateral_rmse_m']:+.3f}%) and has lower heading RMSE, command RMS, actuator-rate RMS and TV "
        'than lateral_student. The nominal rate cap is respected, but a shared maximum-rate bound does not imply shared smoothness.', '',
        'The positive constant increases heading RMSE in all five active regions, '
        'peaking at +8.583% in tire mismatch, while lowering lateral RMSE in each. '
        'The negative constant has lower mean lateral RMSE than the positive '
        'constant on this particular subset; this is an illustration of limited '
        'subset representativeness, not a basis for selecting either sign.', '',
        'The lateral-only objective drops heading/yaw/steering-effort terms, so '
        'improved lateral error alone cannot establish a multi-objective improvement. '
        'These descriptive measurements cannot assign all differences causally to '
        'individual cost terms because gate acceptance and subsequent state histories change.', '',
        'The latency100 metrics match LQR exactly for every method, consistent with '
        'severe-delay fallback. Excluding latency100, the five-active-region changes for '
        'lateral_fixed_p004 are ' + ', '.join(
            f"{k} {active['lateral_fixed_p004']['percent_change_vs_lqr'][k]:+.3f}%" for k in METRICS
        ) + '.', '',
        'Full-grid primary outcome and predeclared selection are separate: the known '
        '1080-episode result is 9.122% lower mean penalized lateral RMSE for '
        'lateral_fixed_p004 and 4.528% for lateral_student versus LQR, with no '
        'learned variant passing predeclared selection. This diagnostic does not '
        'alter that decision or justify opening the reserved split.', '',
        'The JSON includes all ten methods, all six regions, input SHA-256 hashes, '
        'metric definitions, validation residuals, and separate all-six/five-active '
        'aggregates. Regenerate with:', '',
        '```sh',
        'python /tmp/lans-v12-tradeoffs.py --repo /workspace/LANS-webots --output /tmp/lans-v12-tradeoffs.json',
        '```', '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='JSON path; Markdown written beside it with .md suffix')
    args = parser.parse_args()
    repo = args.repo.resolve()
    base = repo / 'integrations/webots/results/revision12-ablation'
    core_path = base / 'source/core.py'
    run_protocol_path = base / 'source/revision12/protocol.json'
    physical_protocol_path = base / 'source/revision6/protocol.json'
    run_protocol = json.loads(run_protocol_path.read_text())
    physical_protocol = json.loads(physical_protocol_path.read_text())
    path = tuple(float(v) for v in physical_protocol['paths']['dlc220'])
    path_values = frozen_path_function(core_path)
    regions, methods = run_protocol['scenarios'], run_protocol['methods']
    with (base / 'pair-0/episodes.csv').open(newline='') as handle:
        summaries = {(r['scenario'], r['method']): r for r in csv.DictReader(handle)
                     if r['repetition'] == '0' and r['speed'] == '25' and r['path'] == 'dlc220'}
    expected_paths = {base / 'pair-0/traces' / f'{region}-{method}.csv.gz'
                      for region in regions for method in methods}
    assert expected_paths == set((base / 'pair-0/traces').glob('*.csv.gz')), 'Unexpected trace coverage'
    result = {
        'label': 'posthoc diagnostic of existing development traces only',
        'scope': {'repetition': 0, 'student_seed': 701, 'speed_m_s': 25,
                  'path': 'dlc220', 'region_count': 6, 'method_count': 10,
                  'trace_count': 60, 'trajectories_per_region_method': 1,
                  'control_period_s': .01, 'initial_actuator_rad': 0.,
                  'all_108_paired_cells_analyzed': False,
                  'new_runs_training_tuning_or_reserved_access': False},
        'limitations': ['One pair, speed and path per region; no generalization to all 108 development cells.',
                        'Descriptive posthoc diagnostics, not selection criteria or formal stability/safety evidence.',
                        'Time samples are not independent replicate experiments; no inferential confidence intervals.'],
        'definitions': {
            'lateral_rmse_m': 'sqrt(mean((true y - reference y)^2)) over post-step rows',
            'heading_rmse_rad': 'sqrt(mean((heading - frozen_core.path_values(x,dlc220)[1])^2)); no wrapping, same as runner failure condition',
            'command_rms_rad': 'sqrt(mean(command^2)) over interval commands',
            'actuator_rate_rms_rad_s': 'sqrt(mean(((actuator_i-actuator_previous)/dt_i)^2)); initial actuator 0 and time 0 included',
            'actuator_total_variation_rad': 'sum(abs(actuator_i-actuator_previous)); initial actuator 0 included',
            'aggregate': 'Equal-region arithmetic mean of each episode metric; not pooled time-sample RMS',
            'percent_change_vs_lqr': '100*(method_metric/LQR_metric-1); negative means lower',
        },
        'source_evaluation': 'AST extraction of exact frozen core reference/path_values bodies; decorator stripped only to avoid numba caches; no simulator import or execution',
        'input_sha256': {}, 'regions': regions, 'methods': methods,
        'by_region': {}, 'aggregate_equal_region_mean': {},
    }
    for file in [core_path, run_protocol_path, physical_protocol_path, base / 'pair-0/episodes.csv']:
        result['input_sha256'][str(file.relative_to(repo))] = digest(file)
    maximum_residuals = {'lateral_rmse': 0., 'max_rate': 0., 'max_command': 0., 'max_actuator': 0., 'reference_y': 0.}
    for region in regions:
        result['by_region'][region] = {}
        for method in methods:
            trace = base / 'pair-0/traces' / f'{region}-{method}.csv.gz'
            result['input_sha256'][str(trace.relative_to(repo))] = digest(trace)
            with gzip.open(trace, 'rt', newline='') as handle:
                rows = list(csv.DictReader(handle))
            assert len(rows) == 1080
            heading_errors, lateral_errors, commands, actuators, rates, increments = [], [], [], [], [], []
            previous_actuator, previous_time = 0., 0.
            for tick, row in enumerate(rows):
                assert int(row['tick']) == tick
                now = float(row['state_time_s'])
                dt = now - previous_time
                assert math.isclose(dt, .01, rel_tol=0, abs_tol=2e-14)
                y_ref, heading_ref, _ = path_values(float(row['x']), path)
                maximum_residuals['reference_y'] = max(maximum_residuals['reference_y'], abs(y_ref-float(row['reference'])))
                lateral_error = float(row['y']) - y_ref
                assert math.isclose(lateral_error, float(row['error']), rel_tol=0, abs_tol=1e-12)
                lateral_errors.append(lateral_error)
                heading_errors.append(float(row['heading'])-heading_ref)
                commands.append(float(row['command']))
                actuator = float(row['actuator'])
                actuators.append(actuator)
                increment = actuator - previous_actuator
                increments.append(increment)
                rates.append(increment / dt)
                previous_actuator, previous_time = actuator, now
            metrics = dict(lateral_rmse_m=rms(lateral_errors), heading_rmse_rad=rms(heading_errors),
                           command_rms_rad=rms(commands), actuator_rate_rms_rad_s=rms(rates),
                           actuator_total_variation_rad=math.fsum(abs(x) for x in increments))
            summary = summaries[(region, method)]
            assert summary['survived'] == 'True'
            assert int(summary['steps']) == len(rows) == int(summary['scheduled_steps'])
            checks = {'lateral_rmse': (metrics['lateral_rmse_m'], float(summary['rmse'])),
                      'max_rate': (max(abs(v) for v in rates), float(summary['max_rate'])),
                      'max_command': (max(abs(v) for v in commands), float(summary['max_command'])),
                      'max_actuator': (max(abs(v) for v in actuators), float(summary['max_actuator']))}
            for name, (derived, recorded) in checks.items():
                difference = abs(derived-recorded)
                maximum_residuals[name] = max(maximum_residuals[name], difference)
                assert difference < 1e-11, (region, method, name, difference)
            assert max(abs(v) for v in rates) <= .3500001
            result['by_region'][region][method] = {
                'samples': len(rows), 'duration_s': previous_time, 'metrics': metrics,
                'heading_rmse_deg': math.degrees(metrics['heading_rmse_rad']),
                'max_actuator_rate_rad_s': max(abs(v) for v in rates),
                'actuator_rms_rad': rms(actuators),
            }
        baseline = result['by_region'][region]['lqr']['metrics']
        for method in methods:
            entry = result['by_region'][region][method]
            entry['percent_change_vs_lqr'] = {k: pct(entry['metrics'][k], baseline[k]) for k in METRICS}
    for name, included in [('all_six_regions', regions),
                           ('five_active_regions', [r for r in regions if r != 'latency100'])]:
        aggregates = {method: {'mean_metrics': {metric: statistics.fmean(
            result['by_region'][region][method]['metrics'][metric] for region in included)
            for metric in METRICS}} for method in methods}
        baseline = aggregates['lqr']['mean_metrics']
        for method in methods:
            aggregates[method]['percent_change_vs_lqr'] = {
                k: pct(aggregates[method]['mean_metrics'][k], baseline[k]) for k in METRICS}
        result['aggregate_equal_region_mean'][name] = aggregates
    for method in methods:
        assert result['by_region']['latency100'][method]['metrics'] == result['by_region']['latency100']['lqr']['metrics']
    result['validation'] = {'all_60_traces_complete': True, 'all_episode_checks_passed': True,
                            'maximum_absolute_residual_vs_recorded': maximum_residuals,
                            'all_severe_latency_metrics_exactly_equal_lqr': True}
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    output.with_suffix('.md').write_text(markdown(result))
    print(json.dumps({'json': str(output), 'notes': str(output.with_suffix('.md')),
                      'validation': result['validation'],
                      'focus_six_region_mean': {m: result['aggregate_equal_region_mean']['all_six_regions'][m] for m in FOCUS}}, indent=2))


if __name__ == '__main__':
    main()
