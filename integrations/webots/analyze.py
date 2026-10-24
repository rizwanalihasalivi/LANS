"""Fail-closed acceptance checks of actual simulator CSVs, not research metrics."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent


def analyze(directory):
    metadata = json.loads((directory / 'provenance.json').read_text())
    for path, digest in metadata['input_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, f'stale input: {path}'
    assert (directory / 'config.json').read_bytes() == (ROOT / 'config.json').read_bytes()
    config = json.loads((ROOT / 'config.json').read_text())
    limits = config['acceptance']
    dt = config['control_period_s']
    summary = {}
    for case, angle in config['cases'].items():
        audit = json.loads((directory / f'{case}-vehicle.json').read_text())
        for name in ('world', 'config'):
            path = ROOT / ('worlds/vehicle_validation.wbt' if name == 'world' else 'config.json')
            assert audit[f'{name}_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest(), f'{case}: stale {name}'
        with (directory / f'{case}.csv').open() as stream:
            rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
        assert len(rows) == round(config['duration_s'] / dt), f'{case}: incomplete run'
        for index, row in enumerate(rows):
            assert all(math.isfinite(v) for v in row.values()), f'{case}: nonfinite sample'
            assert row['step'] == index + 1
            assert math.isclose(row['t_state_s'] - row['t_command_s'], dt, abs_tol=1e-9)
            assert math.isclose(row['t_test_s'], index * dt, abs_tol=1e-9)
            if index:
                assert math.isclose(row['t_state_s'] - rows[index - 1]['t_state_s'], dt, abs_tol=1e-9)
            expected_angle = angle if row['t_test_s'] >= config['steering_start_s'] - 1e-9 else 0
            expected_speed = config['speed_m_s'] if row['t_test_s'] >= config['motion_start_s'] - 1e-9 else 0
            assert row['steering_requested_rad'] == row['steering_applied_rad'] == expected_angle
            assert row['steering_webots_command_rad'] == -expected_angle
            assert row['speed_target_m_s'] == expected_speed
        steady = [row for row in rows if row['t_test_s'] >= 8]
        wb_angle = -angle
        wheelbase = audit['wheelbase_m']
        track = audit['track_front_m']
        expected_left = math.atan(math.tan(wb_angle) / (1 + track * math.tan(wb_angle) / (2 * wheelbase)))
        expected_right = math.atan(math.tan(wb_angle) / (1 - track * math.tan(wb_angle) / (2 * wheelbase)))
        wheel_error = max(abs(row[f'wheel_{side}_sensor_rad'] - target)
                          for row in steady for side, target in [('left', expected_left), ('right', expected_right)])
        speed_error = max(abs(row['speed_truth_m_s'] - config['speed_m_s']) for row in steady)
        assert wheel_error < limits['wheel_angle_error_max_rad'], f'{case}: wheel angle/radian check'
        assert speed_error < limits['speed_error_max_m_s'], f'{case}: speed conversion/tracking check'
        final = rows[-1]
        assert final['x_m'] > 30, f'{case}: insufficient forward motion'
        curvature = mean(row['yaw_rate_rad_s'] / row['speed_truth_m_s'] for row in steady)
        nominal_curvature = math.tan(angle) / wheelbase
        if angle == 0:
            assert max(abs(row['y_m']) for row in rows) < limits['straight_lateral_max_m']
            assert max(abs(row['heading_rad']) for row in rows) < limits['straight_heading_max_rad']
            ratio = None
        else:
            sign = math.copysign(1, angle)
            assert sign * final['heading_rad'] > limits['turn_heading_min_rad'], f'{case}: heading sign'
            assert sign * final['y_m'] > limits['turn_lateral_min_m'], f'{case}: lateral sign'
            ratio = curvature / nominal_curvature
            assert limits['curvature_ratio_min'] < ratio < limits['curvature_ratio_max'], f'{case}: curvature scale'
        summary[case] = {
            'passed': True, 'samples': len(rows), 't_first_state_s': rows[0]['t_state_s'],
            't_final_state_s': final['t_state_s'], 'steering_rad': angle,
            'final_x_m': final['x_m'], 'final_y_m': final['y_m'],
            'max_abs_y_m': max(abs(r['y_m']) for r in rows),
            'final_heading_rad': final['heading_rad'],
            'final_speed_truth_m_s': final['speed_truth_m_s'],
            'steady_speed_truth_mean_m_s': mean(r['speed_truth_m_s'] for r in steady),
            'steady_speed_driver_mean_m_s': mean(r['speed_driver_m_s'] for r in steady),
            'steady_speed_error_max_m_s': speed_error,
            'expected_left_wheel_webots_rad': expected_left,
            'expected_right_wheel_webots_rad': expected_right,
            'steady_wheel_error_max_rad': wheel_error,
            'steady_curvature_mean_per_m': curvature,
            'kinematic_curvature_per_m': nominal_curvature,
            'curvature_ratio': ratio,
        }
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = analyze(args.directory)
    (args.directory / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))
