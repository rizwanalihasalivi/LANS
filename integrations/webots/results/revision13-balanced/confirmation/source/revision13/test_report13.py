"""Synthetic-grid evidence and preregistered-decision tests; no research runs."""
import copy
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest

from common13 import P, methods, noise_id, road_spec, roads, sources
from report13 import (CANDIDATE_CHECKS, COLUMNS, Metrics, assess, candidate_assessment,
                      native_candidate, validate, verify_archive, write_report)


def development_selection():
    name = 'balanced_light_fixed_p004'
    return dict(phase='development', protocol=P, source_commit='a'*40,
                selected_candidate=name, native_candidate=native_candidate(name),
                assessments={name: dict(eligible=True, checks={key: True for key in CANDIDATE_CHECKS})})


def metadata(phase):
    return dict(phase=phase, protocol=P, source_commit='a'*40,
                submission_semantics='every-available-worker-v1', training_steps=0,
                reserved_opened=phase == 'reserved', episodes=P['phases'][phase]['episodes'],
                students={str(seed): {name: 'b'*64 for name in ('student.pt', 'normalization.npz', 'complete.json')}
                          for seed in P['student_seeds']},
                sources={name: 'c'*64 for name in sources()},
                selection=development_selection() if phase == 'reserved' else None,
                selection_sha256='d'*64 if phase == 'reserved' else None)


def sync(row):
    n, total = row['steps'], row['scheduled_steps']
    for metric, sum_key in [('rmse', 'lateral_sq_sum'), ('heading_rmse', 'heading_sq_sum'),
                            ('command_rms', 'command_sq_sum'), ('actuator_rate_rms', 'actuator_rate_sq_sum'),
                            ('yaw_error_rms', 'yaw_error_sq_sum')]:
        row[sum_key] = n*row[metric]**2
    row['penalized_rmse'] = math.sqrt((row['lateral_sq_sum']+(total-n)*6.25)/total)
    row['penalized_heading_rmse'] = math.sqrt((row['heading_sq_sum']+(total-n)*.36)/total)
    count = n//10 if row['method'] != 'lqr' and row['scenario'] != 'latency100' else 0
    row['active_fraction'] = count/n
    row['mean_weight'] = .1*count/n
    row['submissions'] = 0 if row['method'] == 'lqr' else n


def fixture(phase='development'):
    meta = metadata(phase)
    rows = []
    for rep, speed, road, region, method in itertools.product(
            P['repetitions'], P['speeds'], roads(phase), P['scenarios'], methods(phase, meta['selection'])):
        _, length, geometry, sign = road_spec(road)
        n = math.ceil((length/speed+2)/.01)
        lateral = .1 if method == 'lqr' else .09 if method.startswith('lateral_fixed') else .094
        heading = .032 if method.startswith('lateral_fixed') else .0303 if method.startswith('balanced') else .03
        rate = .13 if method.startswith('lateral_fixed') else .102 if method.startswith('balanced') else .1
        variation = 1.3 if method.startswith('lateral_fixed') else 1.02 if method.startswith('balanced') else 1.
        if region == 'latency100':
            lateral, heading, rate, variation = .1, .03, .1, 1.
        row = dict(phase=phase, repetition=rep, seed=P['student_seeds'][rep],
                   noise_id=noise_id(phase, rep, speed, road, region), speed=speed, road=road,
                   geometry=geometry, sign=sign, scenario=region, method=method,
                   survived=True, steps=n, scheduled_steps=n, rmse=lateral, heading_rmse=heading,
                   command_rms=.02, actuator_rate_rms=rate, yaw_error_rms=.01,
                   actuator_total_variation=variation, max_rate=.3, max_command=.2,
                   max_actuator=.1, max_abs_heading=.2, max_abs_error=.3,
                   trajectory_sha256=hashlib.sha256(f'{rep}-{speed}-{road}-{region}'.encode()).hexdigest(),
                   wall_p99_s=.001, max_packet_age_s=0. if method == 'lqr' else .1)
        sync(row)
        assert set(row) == COLUMNS
        rows.append(row)
    return rows, meta


def alter(rows, predicate, **values):
    for row in rows:
        if predicate(row):
            row.update(values)
            sync(row)


def archive(run, rows, meta):
    meta = copy.deepcopy(meta)
    for name in sources():
        path = run/'source'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(P)+'\n').encode() if name == 'revision13/protocol.json' else b'# synthetic source fixture\n'
        path.write_bytes(payload)
        meta['sources'][name] = hashlib.sha256(payload).hexdigest()
    if meta['phase'] == 'reserved':
        path = run/'development-selection.json'
        path.write_text(json.dumps(meta['selection'])+'\n')
        meta['selection_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (run/'complete.json').write_text(json.dumps(meta)+'\n')
    with (run/'episodes.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    return meta


class EvidenceContracts(unittest.TestCase):
    def test_complete_grids_and_predeclared_tie_preference(self):
        for phase, count in [('confirmation', 2160), ('development', 5616), ('reserved', 3024)]:
            rows, meta = fixture(phase)
            checked, result = assess(rows, meta)
            self.assertEqual(len(checked), count)
            self.assertGreater(result['mirror_comparisons'], 0)
            if phase == 'confirmation':
                self.assertTrue(result['replication_pass'])
                self.assertIsNone(result['selected_candidate'])
                self.assertEqual(result['replication_subsets']['original_positive']['lqr']['episodes'], 108)
            else:
                self.assertEqual(result['selected_candidate'], 'balanced_light_fixed_p004')
                self.assertEqual(result['native_candidate'], {'variant': 2, 'residual_rad': .04})
                if phase == 'reserved':self.assertTrue(result['confirmed'])

    def test_missing_duplicate_noise_and_horizon_fail_closed(self):
        rows, meta = fixture()
        for mutation in ('missing', 'duplicate', 'noise', 'horizon', 'orientation'):
            sample = copy.deepcopy(rows)
            if mutation == 'missing':sample.pop()
            elif mutation == 'duplicate':sample[-1] = sample[0].copy()
            elif mutation == 'noise':sample[0]['noise_id'] += 1
            elif mutation == 'horizon':sample[0]['scheduled_steps'] += 1
            else:sample[0]['sign'] *= -1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):validate(sample, meta)

    def test_metric_penalties_bounds_and_severe_trace_guard(self):
        rows, meta = fixture()
        for key, value in [('heading_sq_sum', 1.), ('penalized_rmse', .5), ('max_rate', .36),
                           ('mean_weight', .6), ('actuator_total_variation', 100.), ('command_rms', float('nan'))]:
            sample = copy.deepcopy(rows);sample[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):validate(sample, meta)
        sample = copy.deepcopy(rows)
        row = next(r for r in sample if r['scenario'] == 'latency100' and r['method'] != 'lqr')
        row['trajectory_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'severe'):validate(sample, meta)

    def test_mirror_swaps_fixed_signs_not_student(self):
        rows, meta = fixture()
        # Change one fixed branch, but not its opposite-sign reflection.
        sample = copy.deepcopy(rows)
        row = next(r for r in sample if r['method'] == 'balanced_light_fixed_p004' and r['scenario'] == 'nominal')
        row['rmse'] *= .9;sync(row)
        with self.assertRaisesRegex(ValueError, 'reflection'):validate(sample, meta)
        # An asymmetric old student is allowed and must remain measurable.
        row = next(r for r in rows if r['method'] == 'balanced_light_student' and r['scenario'] == 'nominal')
        row['rmse'] *= .9;sync(row)
        validate(rows, meta)

    def test_all_candidate_screen_requirements(self):
        rows, _ = fixture()
        name = 'balanced_light_fixed_p004'
        def check(sample, expected):
            result = candidate_assessment(Metrics(sample), name, 'development')
            self.assertFalse(result['checks'][expected], expected)
            self.assertFalse(result['eligible'])
        mutations = [
            ('overall_lateral_gain', lambda r:r['scenario'] != 'latency100', {'rmse': .098}),
            ('retain_lateral_gain', lambda r:r['scenario'] != 'latency100', {'rmse': .0951}),
            ('all_three_pair_means_better', lambda r:r['repetition'] == 0 and r['scenario'] != 'latency100', {'rmse': .101}),
            ('each_geometry_orientation_better', lambda r:r['road'] == 'sine120_left' and r['scenario'] != 'latency100', {'rmse': .101}),
            ('nominal_tracking_preserved', lambda r:r['scenario'] == 'nominal', {'rmse': .1001}),
            ('active_region_tracking_preserved', lambda r:r['scenario'] == 'tire_mismatch', {'rmse': .1011}),
            ('overall_heading_preserved', lambda r:r['scenario'] != 'latency100', {'heading_rmse': .031}),
            ('active_region_heading_preserved', lambda r:r['scenario'] == 'tire_mismatch', {'heading_rmse': .0316}),
            ('overall_motion_preserved', lambda r:r['scenario'] != 'latency100', {'actuator_rate_rms': .114}),
            ('active_region_motion_preserved', lambda r:r['scenario'] == 'tire_mismatch', {'actuator_total_variation': 1.151}),
            ('rate_and_tv_reduced_vs_lateral', lambda r:r['scenario'] != 'latency100', {'actuator_total_variation': 1.18}),
        ]
        for expected, predicate, values in mutations:
            sample = copy.deepcopy(rows)
            alter(sample, lambda r:r['method'] == name and predicate(r), **values)
            with self.subTest(check=expected):check(sample, expected)
        sample = copy.deepcopy(rows)
        row = next(r for r in sample if r['method'] == name)
        row['survived'] = False
        check(sample, 'cellwise_survival_preserved')

    def test_failed_cases_remain_with_both_tail_penalties(self):
        rows, meta = fixture()
        for name, road in [('balanced_light_fixed_p004', 'sine120_left'),
                           ('balanced_light_fixed_m004', 'sine120_right')]:
            row = next(r for r in rows if r['method'] == name and r['road'] == road and r['scenario'] == 'nominal')
            row['survived'] = False;row['steps'] -= 1;row['max_abs_error'] = 2.6
            sync(row)
            self.assertGreater(row['penalized_rmse'], row['rmse'])
            self.assertGreater(row['penalized_heading_rmse'], row['heading_rmse'])
        checked, result = assess(rows, meta)
        self.assertEqual(len(checked), 5616)
        self.assertEqual(result['summary']['balanced_light_fixed_p004']['survived'], 431)
        self.assertFalse(result['assessments']['balanced_light_fixed_p004']['eligible'])

    def test_phase_and_selected_candidate_provenance(self):
        rows, meta = fixture()
        for key, value in [('phase', 'confirmation'), ('training_steps', 1), ('reserved_opened', True),
                           ('selection', development_selection()), ('sources', {})]:
            changed = copy.deepcopy(meta);changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):validate(rows, changed)
        rows, meta = fixture('reserved')
        for key, value in [('phase', 'confirmation'), ('selected_candidate', 'lateral_fixed_p004'),
                           ('native_candidate', {'variant':3, 'residual_rad':.04})]:
            changed = copy.deepcopy(meta);changed['selection'][key] = value
            with self.subTest(selection_key=key), self.assertRaises(ValueError):validate(rows, changed)
        changed = copy.deepcopy(meta)
        changed['selection']['assessments']['balanced_light_fixed_p004']['checks']['overall_motion_preserved'] = False
        with self.assertRaises(ValueError):validate(rows, changed)

    def test_archive_hashes_protocol_and_selection_bytes(self):
        rows, meta = fixture('reserved')
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder);complete = archive(run, rows, meta)
            verify_archive(run, complete)
            path = run/'source/revision13/gate13.py';original = path.read_bytes();path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'digest'):verify_archive(run, complete)
            path.write_bytes(original)
            (run/'development-selection.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'selection archive'):verify_archive(run, complete)
        changed = copy.deepcopy(meta);changed['sources']['../outside.py'] = 'a'*64
        with self.assertRaisesRegex(ValueError, 'unsafe'):validate(rows, changed)

    def test_reserved_failure_does_not_reselect_and_reports_are_phase_specific(self):
        rows, meta = fixture('reserved')
        alter(rows, lambda r:r['method'].startswith('balanced_light_fixed') and r['scenario'] != 'latency100', heading_rmse=.034)
        _, result = assess(rows, meta)
        self.assertFalse(result['confirmed'])
        self.assertEqual(result['selected_candidate'], 'balanced_light_fixed_p004')
        self.assertEqual(result['next_action'], 'stop_native_and_learning_no_reselection')
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder);complete = archive(run, rows, meta);write_report(run)
            verification = json.loads((run/'verification.json').read_text())
            self.assertTrue(verification['verified'])
            self.assertEqual(verification['phase'], 'reserved')
            self.assertEqual(verification['protocol'], P)
            self.assertEqual(verification['selection_sha256'], complete['selection_sha256'])
            self.assertEqual(verification['selected_candidate'], 'balanced_light_fixed_p004')
            self.assertEqual(verification['native_candidate'], {'variant':2, 'residual_rad':.04})
            self.assertFalse(verification['confirmed'])
            self.assertFalse((run/'selection.json').exists())
        rows, meta = fixture('confirmation')
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder);archive(run, rows, meta);result = write_report(run)
            self.assertIsNone(result['selected_candidate'])
            self.assertFalse((run/'selection.json').exists())
            self.assertIn('original_positive', (run/'report.md').read_text())


if __name__ == '__main__':
    unittest.main()
