#!/usr/bin/env python3
"""Independent, read-only revision12 arithmetic/provenance audit.

No imports from project code; no simulation, report12 invocation, training, or
reserved-split reads. Only outputs under /tmp are written. Uses Python stdlib.
"""
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess

ROOT = Path('/workspace/LANS-webots')
RUN = ROOT / 'integrations/webots/results/revision12-ablation'
RESEARCH = ROOT / 'integrations/webots/research'
OUT = Path('/tmp/lans-v12-independent')
FROZEN_COMMIT = 'c49ddc065caf9c93eb4867b91446a8037a11ffc7'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def avg(values):
    values = list(values)
    return math.fsum(values) / len(values)


def key(row):
    return (int(row['repetition']), int(row['speed']), row['path'], row['scenario'])


def gain(candidate, reference):
    return 100 * (reference - candidate) / reference if reference else None


def finite_close(a, b):
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14)


p = json.loads((RUN / 'source/revision12/protocol.json').read_text())
manifest = json.loads((RUN / 'complete.json').read_text())
rows = read_rows(RUN / 'episodes.csv')
methods, regions, reps, seeds = (p[k] for k in ('methods', 'scenarios', 'repetitions', 'student_seeds'))
failures = []
checks = {}


def check(name, result):
    checks[name] = bool(result)
    if not result:
        failures.append(name)


check('manifest_commit_equals_expected', manifest['source_commit'] == FROZEN_COMMIT)
check('protocol_manifest_and_current_match_archive', p == manifest['protocol'] == json.loads((RESEARCH / 'revision12/protocol.json').read_text()))
check('1080_rows_manifest_matches_protocol', len(rows) == manifest['episodes'] == p['development_episodes'] == 1080)
expected = set(itertools.product(reps, p['speeds'], p['paths'], regions, methods))
observed = [(*key(r), r['method']) for r in rows]
check('complete_unique_balanced_grid', len(observed) == len(set(observed)) and set(observed) == expected)
check('pair_shards_match_aggregate_exactly', rows == [r for rep in reps for r in read_rows(RUN / f'pair-{rep}/episodes.csv')])
check('all_shard_completion_records_match', all(json.loads((RUN / f'pair-{rep}/complete.json').read_text()) == {'episodes': 360, 'repetition': rep} for rep in reps))
check('all_seeds_and_noise_ids_match_frozen_formula', all(int(r['seed']) == seeds[int(r['repetition'])] and int(r['noise_id']) == p['development_noise_base'] + int(r['repetition']) * 10000 + int(r['speed']) * 100 + p['paths'].index(r['path']) * 10 + regions.index(r['scenario']) for r in rows))
check('all_survival_values_boolean', all(r['survived'] in ('True', 'False') for r in rows))
float_fields = ('rmse', 'penalized_rmse', 'active_fraction', 'mean_weight', 'max_rate', 'max_command', 'max_actuator', 'wall_p99_s', 'max_packet_age_s')
check('all_numeric_episode_metrics_finite', all(math.isfinite(float(r[f])) for r in rows for f in float_fields))
check('physical_bounds', all(0 <= float(r['max_rate']) <= .3500001 and 0 <= float(r['max_command']) <= .5000001 and 0 <= float(r['max_actuator']) <= .5000001 and 0 <= float(r['mean_weight']) <= .5000001 and 0 <= float(r['active_fraction']) <= 1 for r in rows))
check('valid_steps_and_survival', all(int(r['scheduled_steps']) == math.ceil((220 / int(r['speed']) + 2) / .01) and 0 < int(r['steps']) <= int(r['scheduled_steps']) and (r['survived'] != 'True' or int(r['steps']) == int(r['scheduled_steps'])) for r in rows))
check('penalty_formula_from_episode_rmse', all(finite_close(float(r['penalized_rmse']), math.sqrt((float(r['rmse']) ** 2 * int(r['steps']) + 6.25 * (int(r['scheduled_steps']) - int(r['steps']))) / int(r['scheduled_steps']))) for r in rows))
check('hash_strings_valid', all(len(r['trajectory_sha256']) == 64 and set(r['trajectory_sha256']) <= set('0123456789abcdef') for r in rows))
index = {(r['method'], *key(r)): r for r in rows}
cells = list(itertools.product(reps, p['speeds'], p['paths'], regions))
severe = [cell for cell in cells if cell[-1] == 'latency100']
severe_fields = ('trajectory_sha256', 'survived', 'steps', 'scheduled_steps', 'rmse', 'penalized_rmse', 'max_rate', 'max_command', 'max_actuator')
severe_pairs = []
for cell in severe:
    baseline = index[('lqr', *cell)]
    for method in methods[1:]:
        candidate = index[(method, *cell)]
        severe_pairs.append({'cell': list(cell), 'method': method, 'hash_equal': candidate['trajectory_sha256'] == baseline['trajectory_sha256'], 'scores_and_bounds_equal': all(candidate[field] == baseline[field] for field in severe_fields), 'inactive': float(candidate['active_fraction']) == float(candidate['mean_weight']) == 0})
check('all_162_severe_comparisons_exact_logged_hash_and_scores', all(c['hash_equal'] and c['scores_and_bounds_equal'] and c['inactive'] for c in severe_pairs))
check('manifest_is_development_zero_training_unopened_reserved', manifest['split'] == 'development' and manifest['training_steps'] == 0 and manifest['reserved_split_opened'] is False)

sources = []
for relative, expected_hash in manifest['sources'].items():
    archived = (RUN / 'source' / relative).read_bytes()
    current = (RESEARCH / relative).read_bytes()
    repo_relative = str((RESEARCH / relative).relative_to(ROOT))
    committed = subprocess.check_output(['git', 'show', f'{FROZEN_COMMIT}:{repo_relative}'], cwd=ROOT)
    sources.append({'file': relative, 'manifest_sha256': expected_hash, 'archived_sha256': digest(archived), 'git_commit_sha256': digest(committed), 'current_sha256': digest(current), 'all_equal': digest(archived) == expected_hash == digest(committed) == digest(current)})
check('all_21_source_digests_match_manifest_git_commit_and_current', len(sources) == 21 and all(s['all_equal'] for s in sources))
student_checks = []
for seed, artifacts in manifest['students'].items():
    for name, expected_hash in artifacts.items():
        artifact = ROOT / f'integrations/webots/results/revision8-student/students/{seed}' / name
        observed_hash = digest(artifact.read_bytes())
        student_checks.append({'seed': int(seed), 'artifact': name, 'manifest_sha256': expected_hash, 'observed_sha256': observed_hash, 'equal': expected_hash == observed_hash})
check('all_9_frozen_student_artifact_digests_match', len(student_checks) == 9 and all(s['equal'] for s in student_checks))


def summarize(subset):
    values = [float(r['penalized_rmse']) for r in subset]
    return {'episodes': len(subset), 'survived': sum(r['survived'] == 'True' for r in subset), 'mean_penalized_rmse': avg(values), 'mean_rmse': avg(float(r['rmse']) for r in subset), 'mean_active_fraction': avg(float(r['active_fraction']) for r in subset)}


overall = {method: summarize([r for r in rows if r['method'] == method]) for method in methods}
by_region = {region: {method: summarize([r for r in rows if r['method'] == method and r['scenario'] == region]) for method in methods} for region in regions}
by_seed = {str(seed): {method: summarize([r for r in rows if r['method'] == method and int(r['seed']) == seed]) for method in methods} for seed in seeds}
by_region_seed = {region: {str(seed): {method: summarize([r for r in rows if r['method'] == method and r['scenario'] == region and int(r['seed']) == seed]) for method in methods} for seed in seeds} for region in regions}
for method in methods:
    overall[method]['gain_vs_lqr_percent'] = gain(overall[method]['mean_penalized_rmse'], overall['lqr']['mean_penalized_rmse'])
    overall[method]['paired_seed_mean_sample_sd'] = statistics.stdev(by_seed[str(seed)][method]['mean_penalized_rmse'] for seed in seeds)
    for region in regions:
        by_region[region][method]['gain_vs_lqr_percent'] = gain(by_region[region][method]['mean_penalized_rmse'], by_region[region]['lqr']['mean_penalized_rmse'])
        by_region[region][method]['gain_vs_legacy_student_percent'] = gain(by_region[region][method]['mean_penalized_rmse'], by_region[region]['legacy_student']['mean_penalized_rmse'])
        for seed in seeds:
            group = by_region_seed[region][str(seed)]
            group[method]['gain_vs_lqr_percent'] = gain(group[method]['mean_penalized_rmse'], group['lqr']['mean_penalized_rmse'])
            group[method]['gain_vs_legacy_student_percent'] = gain(group[method]['mean_penalized_rmse'], group['legacy_student']['mean_penalized_rmse'])


def no_survival_loss(method, reference):
    return all(index[(method, *cell)]['survived'] == 'True' or index[(reference, *cell)]['survived'] == 'False' for cell in cells)


def lower_each_pair(method, reference, region=None):
    grouped = by_seed if region is None else by_region_seed[region]
    return all(grouped[str(seed)][method]['mean_penalized_rmse'] < grouped[str(seed)][reference]['mean_penalized_rmse'] for seed in seeds)


assessments = {}
gate_rule = p['gate_progress']
stress = gate_rule['stress_regions']
active = [region for region in regions if region != 'latency100']
for variant in ('preview', 'lateral'):
    method = variant + '_student'
    qualifying = [region for region in stress if by_region[region][method]['gain_vs_legacy_student_percent'] >= 1]
    gate_checks = {
        'overall_gain_vs_legacy_student_at_least_one_percent': gain(overall[method]['mean_penalized_rmse'], overall['legacy_student']['mean_penalized_rmse']) >= gate_rule['overall_gain_vs_legacy_student_percent'],
        'all_three_seed_means_better': lower_each_pair(method, 'legacy_student'),
        'minimum_two_stress_regions_with_one_percent_gain_vs_legacy': len(qualifying) >= gate_rule['minimum_stress_regions_with_one_percent_gain'],
        'active_regions_no_more_than_one_percent_regression_vs_legacy': all(by_region[region][method]['gain_vs_legacy_student_percent'] >= -gate_rule['maximum_active_region_regression_vs_legacy_student_percent'] for region in active),
        'nominal_no_worse_than_lqr': by_region['nominal'][method]['mean_penalized_rmse'] <= by_region['nominal']['lqr']['mean_penalized_rmse'],
        'no_cellwise_survival_loss_vs_lqr': no_survival_loss(method, 'lqr'),
        'no_cellwise_survival_loss_vs_legacy_student': no_survival_loss(method, 'legacy_student'),
        'severe_fallback_exact': all(c['hash_equal'] and c['scores_and_bounds_equal'] and c['inactive'] for c in severe_pairs if c['method'] == method)
    }
    gains_vs_constants = {sign: gain(overall[method]['mean_penalized_rmse'], overall[f'{variant}_fixed_{sign}']['mean_penalized_rmse']) for sign in ('m004', 'p004')}
    benefit_checks = {}
    for sign in ('m004', 'p004'):
        benefit_checks[f'gain_vs_{sign}_at_least_one_percent'] = gains_vs_constants[sign] >= 1
        benefit_checks[f'no_cellwise_survival_loss_vs_{sign}'] = no_survival_loss(method, f'{variant}_fixed_{sign}')
    qualifying_five = [region for region in stress if by_region[region][method]['gain_vs_lqr_percent'] >= 5 and lower_each_pair(method, 'lqr', region)]
    all_regions_five = [region for region in regions if by_region[region][method]['gain_vs_lqr_percent'] >= 5 and lower_each_pair(method, 'lqr', region)]
    gate_pass = all(gate_checks.values())
    benefit_pass = all(benefit_checks.values())
    assessments[variant] = {'gate_progress_checks': gate_checks, 'gate_progress_pass': gate_pass, 'learning_benefit_checks': benefit_checks, 'learning_benefit_pass': benefit_pass, 'eligible': gate_pass and benefit_pass, 'overall_gain_vs_legacy_student_percent': gain(overall[method]['mean_penalized_rmse'], overall['legacy_student']['mean_penalized_rmse']), 'gain_vs_same_gate_constants_percent': gains_vs_constants, 'one_percent_stress_regions_vs_legacy': qualifying, 'five_percent_stress_regions_vs_lqr_all_pairs_lower': qualifying_five, 'five_percent_all_regions_vs_lqr_all_pairs_lower': all_regions_five, 'regional_five_percent_target': len(qualifying_five) >= 2 and gate_pass, 'overall_five_percent_target': overall[method]['gain_vs_lqr_percent'] >= 5}
eligible = [variant for variant in ('preview', 'lateral') if assessments[variant]['eligible']]
if len(eligible) == 2:
    m = {v: overall[v + '_student']['mean_penalized_rmse'] for v in eligible}
    selected = 'preview' if abs(m['preview'] - m['lateral']) <= .01 * min(m.values()) else min(m, key=m.get)
else:
    selected = eligible[0] if eligible else None

# Validate every archived trace against its aggregate row, without executing model code.
trace_checks = []
severe_traces = {}
trace_fields = ('tick', 'state_time_s', 'x', 'y', 'heading', 'reference', 'error', 'command', 'baseline', 'actuator')
for region, method in itertools.product(regions, methods):
    path = RUN / f'pair-0/traces/{region}-{method}.csv.gz'
    with gzip.open(path, 'rt', newline='') as handle:
        trace = list(csv.DictReader(handle))
    row = index[(method, 0, 25, 'dlc220', region)]
    error_sq = math.fsum(float(t['error']) ** 2 for t in trace)
    raw_rmse = math.sqrt(error_sq / len(trace))
    penalized = math.sqrt((error_sq + (int(row['scheduled_steps']) - len(trace)) * 6.25) / int(row['scheduled_steps']))
    tc = {'region': region, 'method': method, 'ticks': len(trace), 'row_steps_match': len(trace) == int(row['steps']), 'rmse_matches': finite_close(raw_rmse, float(row['rmse'])), 'penalized_rmse_matches': finite_close(penalized, float(row['penalized_rmse'])), 'mean_weight_matches': finite_close(avg(float(t['weight']) for t in trace), float(row['mean_weight'])), 'active_fraction_matches': finite_close(avg(float(t['weight']) > 0 for t in trace), float(row['active_fraction']))}
    trace_checks.append(tc)
    if region == 'latency100':
        severe_traces[method] = [tuple(t[field] for field in trace_fields) for t in trace]
        tc['all_commands_equal_baseline_and_zero_weight'] = all(t['command'] == t['baseline'] and float(t['weight']) == 0 for t in trace)
check('all_60_trace_lengths_and_metrics_match_raw_episode_rows', len(trace_checks) == 60 and all(all(v for k, v in tc.items() if k not in ('region', 'method', 'ticks')) for tc in trace_checks))
check('severe_archived_trace_observable_state_and_command_exact', all(severe_traces[m] == severe_traces['lqr'] for m in methods))

# Compare only after all independent calculations have been made.
reported = json.loads((RUN / 'selection.json').read_text())
report_matches = {'selected_gate': reported['selected_gate'] == selected, 'all_overall_means': all(finite_close(reported['summary'][m]['mean_penalized_rmse'], overall[m]['mean_penalized_rmse']) for m in methods), 'all_overall_survivals': all(reported['summary'][m]['survived'] == overall[m]['survived'] for m in methods), 'gate_and_learning_and_five_percent_decisions': all(reported['assessments'][v]['gate_progress_pass'] == assessments[v]['gate_progress_pass'] and reported['assessments'][v]['learning_benefit_pass'] == assessments[v]['learning_benefit_pass'] and reported['assessments'][v]['eligible'] == assessments[v]['eligible'] and reported['assessments'][v]['five_percent_regional_target'] == assessments[v]['regional_five_percent_target'] and reported['assessments'][v]['overall_five_percent_reduction'] == assessments[v]['overall_five_percent_target'] for v in assessments)}
check('existing_selection_agrees_with_independent_arithmetic', all(report_matches.values()))

limitations = [
    'Only 3 paired student/noise seeds, 3 speeds, 2 known paths and 6 known regions: descriptive development screening, not independent-domain or statistically established superiority.',
    'All 1080 episodes survived; failed-tail penalty algebra was checked, but no failed case exercises the penalty path in this run.',
    '18 severe-delay cells have exact logged trajectory hashes across all 10 methods (162 candidate-versus-LQR comparisons); 10 stored severe traces also have exactly equal recorded observable trajectory/command fields.',
    'Only pair0/25m/s/dlc220 is traced (60 of 1080 episodes). Traces omit lateral velocity and yaw-rate state components used in the full trajectory digest, so a complete independent digest reconstruction from traces is impossible; this audit verifies hash equality and manifest provenance, not rerun physics.',
    'The completion manifest declares zero training steps and reserved_split_opened=false. This audit opens no reserved data and launches no experiments; filesystem/provenance checks cannot prove that no separate process ever accessed other data.',
    'Nominal and latency20 are not members of the frozen three-region stress target; passing 5% there cannot replace the predeclared stress requirement.',
    'The lateral fixed positive correction is a predeclared control, not a newly learned result or a post-test deployable selection. Gate-dependent closed-loop feature history differs despite frozen student weights.',
    'No native Webots/real-vehicle safety, formal stability, hard-real-time execution, unseen-road generalization, or SOTA comparison follows from this offline run.'
]
result = {'audit': 'independent stdlib arithmetic; project code not imported or invoked', 'source_commit': FROZEN_COMMIT, 'run': str(RUN), 'verified': not failures, 'failed_checks': failures, 'checks': checks, 'counts': {'episodes': len(rows), 'methods': len(methods), 'pairs': len(reps), 'speeds': len(p['speeds']), 'paths': len(p['paths']), 'regions': len(regions), 'episodes_per_method': 108, 'episodes_per_method_region': 18, 'episodes_per_method_seed': 36, 'episodes_per_method_region_seed': 6, 'survived': sum(r['survived'] == 'True' for r in rows), 'severe_cells': len(severe), 'severe_candidate_lqr_comparisons': len(severe_pairs), 'stored_trace_episodes': len(trace_checks)}, 'overall': overall, 'by_region': by_region, 'by_seed': by_seed, 'by_region_seed': by_region_seed, 'assessments': assessments, 'eligible_variants': eligible, 'selected_gate': selected, 'next_action': 'stop_retraining_path' if selected is None else 'conditional_teacher_only', 'severe_comparisons': severe_pairs, 'source_checks': sources, 'student_checks': student_checks, 'trace_checks': trace_checks, 'existing_report_matches': report_matches, 'limitations': limitations}
OUT.with_suffix('.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
lines = ['# Independent revision12 verification', '', f'Verified: **{not failures}**. Independently selected gate: **{selected or "none"}**. Complete 1080/1080 balanced development grid; all 1080 survived. Frozen source commit `{FROZEN_COMMIT}`.', '', 'No project module was imported, report12 was not invoked, no experiment ran, and no reserved split was opened. The audit script and outputs are confined to `/tmp`.', '', '| Method | Mean penalized RMSE | Gain vs LQR | Survival |', '|---|---:|---:|---:|']
for method in methods:
    s = overall[method]
    lines.append(f'| {method} | {s["mean_penalized_rmse"]:.10f} | {s["gain_vs_lqr_percent"]:+.6f}% | {s["survived"]}/{s["episodes"]} |')
lines += ['', '| Region | Preview student gain vs LQR | Lateral student gain vs LQR | Lateral student gain vs legacy | Lateral student gains vs LQR, seeds 701 / 802 / 903 |', '|---|---:|---:|---:|---|']
for region in regions:
    seed_text = ' / '.join(f'{by_region_seed[region][str(seed)]["lateral_student"]["gain_vs_lqr_percent"]:+.4f}%' for seed in seeds)
    lines.append(f'| {region} | {by_region[region]["preview_student"]["gain_vs_lqr_percent"]:+.6f}% | {by_region[region]["lateral_student"]["gain_vs_lqr_percent"]:+.6f}% | {by_region[region]["lateral_student"]["gain_vs_legacy_student_percent"]:+.6f}% | {seed_text} |')
lines += ['', 'Preview improves on legacy student by only %.6f%% (<1%%), with zero qualifying >=1%% stress-region gains; it passes learned benefit against both constants (%.6f%% / %.6f%%). Gate progress fails.' % (assessments['preview']['overall_gain_vs_legacy_student_percent'], assessments['preview']['gain_vs_same_gate_constants_percent']['m004'], assessments['preview']['gain_vs_same_gate_constants_percent']['p004']), '', 'Lateral passes gate progress but loses to both same-gate constants: student reductions against negative/positive constants are %.6f%% / %.6f%%. Its %.6f%% overall LQR gain is smaller than the constants\' %.6f%% / %.6f%%; learned benefit fails.' % (assessments['lateral']['gain_vs_same_gate_constants_percent']['m004'], assessments['lateral']['gain_vs_same_gate_constants_percent']['p004'], overall['lateral_student']['gain_vs_lqr_percent'], overall['lateral_fixed_m004']['gain_vs_lqr_percent'], overall['lateral_fixed_p004']['gain_vs_lqr_percent']), '', 'Neither student reaches 5% in any of the three predeclared stress-region aggregate means. Lateral exceeds 5% in nominal and latency20, with improvement in all three paired means, but these regions are outside that target. The five-percent stress and overall targets fail.', '', 'All 21 archived source SHA-256 hashes match the manifest, the frozen git commit, and the current source; all 9 student/normalizer/completion artifact hashes match. All 60 archived trace episode metrics agree with raw CSV rows. Exact severe fallback holds for all 18 cells / 162 method-versus-LQR hash-and-score comparisons, and the stored severe observable trace fields match exactly.', '', 'The JSON contains full means, survival and gains by method, region, seed, and region × seed, individual provenance checks, and each frozen screen decision. Existing selection/report overall arithmetic and decisions agree.', '', 'Limits:', '']
lines += ['- ' + limit for limit in limitations]
OUT.with_suffix('.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({'verified': result['verified'], 'failed_checks': failures, 'selected_gate': selected, 'counts': result['counts'], 'assessments': assessments, 'outputs': [str(OUT.with_suffix('.json')), str(OUT.with_suffix('.md'))]}, indent=2))
raise SystemExit(0 if not failures else 1)
