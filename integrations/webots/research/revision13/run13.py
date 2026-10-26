"""Frozen confirmation/development/conditional-reserved balanced-control study."""
import argparse
import concurrent.futures
import csv
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

from common13 import (HERE, RESEARCH, ROOT, P, G, RESULTS, sha, roads, road_spec,
                      noise_id, method_spec, methods, student_hashes, sources)
sys.path.insert(0, str(RESEARCH / 'revision8'))
import bootstrap
import numpy as np
import torch
import numba
from comparison import configure_lqr
from core import GAINS
from kernels import initial_executor, lqr
from plant import advance
from student import load
from dynamics13 import path_values13, measure13, features13
from gate13 import execution_step13


def load_selection(path):
    """Reserved data require an eligible selection committed before execution."""
    raw = path.read_bytes()
    selection = json.loads(raw)
    if selection.get('phase') != 'development' or selection.get('protocol') != P:
        raise ValueError('selection must be from this frozen development protocol')
    chosen = selection.get('selected_candidate')
    if chosen not in P['selection_candidates']:
        raise ValueError('no eligible balanced candidate; reserved split stays closed')
    if selection.get('assessments', {}).get(chosen, {}).get('eligible') is not True:
        raise ValueError('selected candidate did not pass development')
    _, variant, proposer = method_spec(chosen)
    expected = dict(variant=variant, residual_rad=.04 if proposer == 'fixed_p004' else -.04)
    if selection.get('native_candidate') != expected:
        raise ValueError('selection controller identity mismatch')
    relative = path.resolve().relative_to(ROOT)
    committed = subprocess.check_output(['git', 'show', 'HEAD:' + str(relative)], cwd=ROOT)
    if committed != raw:
        raise ValueError('commit the exact development selection before opening reserved data')
    freeze = selection.get('source_commit', '')
    if not re.fullmatch(r'[0-9a-f]{40}', freeze):
        raise ValueError('development executable freeze is missing')
    frozen_paths = [RESEARCH/name for name in sources()]
    frozen_paths += [RESULTS/f'revision8-student/students/{seed}'/name
                     for seed in P['student_seeds']
                     for name in ('student.pt', 'normalization.npz', 'complete.json')]
    for artifact in frozen_paths:
        relative = artifact.relative_to(ROOT)
        original = subprocess.check_output(['git', 'show', freeze+':'+str(relative)], cwd=ROOT)
        if artifact.read_bytes() != original:
            raise ValueError('selected source/model changed before reserved run: '+str(relative))
    return selection, hashlib.sha256(raw).hexdigest()


def episode(phase, method, repetition, speed, road, region, model, gains, trace=None):
    case = G['scenarios'][region]
    path, length, geometry, sign = road_spec(road)
    scheduled = int(np.ceil((length / speed + 2) / .01))
    identity = noise_id(phase, repetition, speed, road, region)
    scales = np.array([.03, np.deg2rad(.17), .01, .1]) * case['noise']
    actual = np.random.default_rng(identity).normal(0, scales, (scheduled, 4))
    actual[:, :3] *= sign
    y, heading, _ = path_values13(0., path)
    state = np.array([0., y + .15*sign, heading + .01*sign, 0., 0., 0.])
    estimate, cov, previous = np.zeros(4), np.eye(4)*.01, np.zeros(4)
    worker = initial_executor()
    _, variant, proposer = method_spec(method)
    sums = dict(lateral_sq_sum=0., heading_sq_sum=0., command_sq_sum=0.,
                actuator_rate_sq_sum=0., yaw_error_sq_sum=0.)
    tv = active = weight_sum = 0.
    max_rate = max_command = max_actuator = max_heading = max_error = max_age = 0.
    submissions, failed, records, runtimes = 0, False, [], []
    trajectory = hashlib.sha256()
    for tick in range(scheduled):
        raw_v = (max(5., previous[3]) if case['sensor_delay_steps'] and tick
                 else max(5., speed + actual[tick, 3]))
        estimate, cov, previous, v, k = measure13(
            state, float(speed), path, actual[tick], case['sensor_delay_steps'],
            estimate, cov, previous, tick == 0, float(case['noise']))
        observed = features13(state, estimate, raw_v, path, worker, tick, case['service_ticks'])
        baseline, gain = lqr(estimate, v, k, gains)
        if not np.isfinite([*estimate, *observed, baseline, v, k]).all():
            raise FloatingPointError('nonfinite controller input is a run-integrity failure')
        available = worker[7] < 0 or worker[6] <= tick*.01 + 1e-9
        proposal = 0.
        started = time.perf_counter()
        if available:
            if proposer == 'fixed_m004':
                proposal = -.04
            elif proposer == 'fixed_p004':
                proposal = .04
            elif proposer == 'student':
                action, _ = model.predict(observed, deterministic=True)
                if np.asarray(action).shape != (1,) or not np.isfinite(action).all():
                    raise ValueError('finite normalized residual required')
                proposal = .08 * float(np.clip(action[0], -1., 1.))
        if method == 'lqr':
            command, weight, reason, submitted = baseline, 0., 10, False
        else:
            command, weight, reason, submitted = execution_step13(
                worker, tick*.01, proposal, case['service_ticks'], baseline,
                estimate, state[5], v, k, gain, variant)
        runtimes.append(time.perf_counter()-started)
        submissions += int(submitted)
        if worker[3] >= 0:
            max_age = max(max_age, tick*.01-worker[4])
        if region == 'latency100' and (command != baseline or weight != 0.):
            raise AssertionError('severe-delay fallback violated')
        old_actuator = state[5]
        state = advance(state, command, float(speed), case['mu'], case['stiffness'])
        reference, reference_heading, curve = path_values13(state[0], path)
        error, heading_error = state[1]-reference, state[2]-reference_heading
        rate = (state[5]-old_actuator)/.01
        yaw_error = state[4]-speed*curve
        if not np.isfinite([*state, command, error, heading_error, rate, yaw_error]).all():
            raise FloatingPointError('nonfinite state is a run-integrity failure')
        sums['lateral_sq_sum'] += error*error
        sums['heading_sq_sum'] += heading_error*heading_error
        sums['command_sq_sum'] += command*command
        sums['actuator_rate_sq_sum'] += rate*rate
        sums['yaw_error_sq_sum'] += yaw_error*yaw_error
        tv += abs(state[5]-old_actuator)
        active += weight > 0
        weight_sum += weight
        max_rate, max_command = max(max_rate, abs(rate)), max(max_command, abs(command))
        max_actuator = max(max_actuator, abs(state[5]))
        max_heading, max_error = max(max_heading, abs(heading_error)), max(max_error, abs(error))
        trajectory.update(np.asarray([command, *state], dtype='<f8').tobytes())
        if trace is not None:
            records.append(dict(tick=tick, state_time_s=(tick+1)*.01,
                x=state[0], y=state[1], heading=state[2], vy=state[3], yaw_rate=state[4],
                actuator=state[5], reference=reference, reference_heading=reference_heading,
                error=error, heading_error=heading_error, actuator_rate=rate,
                command=command, baseline=baseline, weight=weight, reason=reason,
                proposal=proposal, submitted=submitted, packet_sequence=worker[3],
                observed_s=worker[4] if worker[3] >= 0 else '',
                age_s=tick*.01-worker[4] if worker[3] >= 0 else '', pending_sequence=worker[7]))
        if abs(error) > 2.5 or abs(heading_error) > .6:
            failed = True
            break
    steps = tick+1
    if max_rate > .3500001 or max_command > .5000001 or max_actuator > .5000001:
        raise AssertionError('physical limits violated')
    if trace is not None:
        with gzip.open(trace, 'wt', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=records[0], lineterminator='\n')
            writer.writeheader()
            writer.writerows(records)
    return dict(phase=phase, repetition=repetition, seed=P['student_seeds'][repetition],
        noise_id=identity, speed=speed, road=road, geometry=geometry, sign=sign,
        scenario=region, method=method, survived=not failed, steps=steps,
        scheduled_steps=scheduled, **sums, actuator_total_variation=tv,
        rmse=float(np.sqrt(sums['lateral_sq_sum']/steps)),
        penalized_rmse=float(np.sqrt((sums['lateral_sq_sum']+(scheduled-steps)*6.25)/scheduled)),
        heading_rmse=float(np.sqrt(sums['heading_sq_sum']/steps)),
        penalized_heading_rmse=float(np.sqrt((sums['heading_sq_sum']+(scheduled-steps)*.36)/scheduled)),
        command_rms=float(np.sqrt(sums['command_sq_sum']/steps)),
        actuator_rate_rms=float(np.sqrt(sums['actuator_rate_sq_sum']/steps)),
        yaw_error_rms=float(np.sqrt(sums['yaw_error_sq_sum']/steps)),
        active_fraction=active/steps, mean_weight=weight_sum/steps,
        max_rate=max_rate, max_command=max_command, max_actuator=max_actuator,
        max_abs_heading=max_heading, max_abs_error=max_error,
        trajectory_sha256=trajectory.hexdigest(), wall_p99_s=float(np.quantile(runtimes, .99)),
        submissions=submissions, max_packet_age_s=max_age)


def shard(phase, repetition, output, selection):
    configure_lqr()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    gains = np.array([GAINS[v] for v in (15, 20, 25)])
    model = load(RESULTS / f'revision8-student/students/{P["student_seeds"][repetition]}')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'traces').mkdir()
    count = 0
    with (output / 'episodes.csv').open('w', newline='') as handle:
        writer = None
        for speed, road, region in itertools.product(P['speeds'], roads(phase), P['scenarios']):
            for method in methods(phase, selection):
                trace = (output / 'traces' / f'{road}-{region}-{method}.csv.gz'
                         if repetition == 0 and speed == 25 and region in ('nominal', 'tire_mismatch', 'latency100') else None)
                row = episode(phase, method, repetition, speed, road, region, model, gains, trace)
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=row, lineterminator='\n')
                    writer.writeheader()
                writer.writerow(row)
                handle.flush()
                count += 1
            print(phase, repetition, speed, road, region, count, flush=True)
    expected = P['phases'][phase]['episodes']//len(P['repetitions'])
    assert count == expected
    (output / 'complete.json').write_text(json.dumps(dict(episodes=count, repetition=repetition, phase=phase))+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=list(P['phases']), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--repetition', type=int, choices=P['repetitions'])
    args = parser.parse_args()
    selection, selection_digest = None, None
    if args.phase == 'reserved':
        if args.selection is None:
            raise ValueError('reserved phase requires committed development selection')
        selection, selection_digest = load_selection(args.selection.resolve())
    elif args.selection is not None:
        raise ValueError('selection belongs only to reserved phase')
    output = args.output.resolve()
    if args.repetition is not None:
        shard(args.phase, args.repetition, output, selection)
        return
    source_names = sources()
    tracked = [str((RESEARCH/name).relative_to(ROOT)) for name in source_names]
    tracked += [str((RESULTS/f'revision8-student/students/{seed}'/name).relative_to(ROOT))
                for seed in P['student_seeds']
                for name in ('student.pt', 'normalization.npz', 'complete.json')]
    subprocess.run(['git', 'ls-files', '--error-unmatch', '--', *tracked], cwd=ROOT,
                   stdout=subprocess.DEVNULL, check=True)
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', *tracked], cwd=ROOT, check=True)
    source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    students = student_hashes()
    output.mkdir(parents=True, exist_ok=False)
    source_hashes = {}
    for name in source_names:
        destination = output/'source'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RESEARCH/name, destination)
        source_hashes[name] = sha(RESEARCH/name)
    if selection is not None:
        shutil.copyfile(args.selection, output/'development-selection.json')
    started = time.time()

    def job(repetition):
        env = os.environ.copy()
        env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        destination = output/f'pair-{repetition}'
        command = [sys.executable, str(HERE/'run13.py'), '--phase', args.phase,
                   '--output', str(destination), '--repetition', str(repetition)]
        if args.selection:
            command += ['--selection', str(args.selection.resolve())]
        with (output/f'pair-{repetition}.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        with (destination/'episodes.csv').open() as handle:
            return list(csv.DictReader(handle))

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = [row for part in pool.map(job, P['repetitions']) for row in part]
    assert len(rows) == P['phases'][args.phase]['episodes']
    assert students == student_hashes(), 'student artifacts changed'
    assert all(sha(RESEARCH/name) == value for name, value in source_hashes.items()), 'source changed'
    with (output/'episodes.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    complete = dict(phase=args.phase, episodes=len(rows), protocol=P, source_commit=source_commit,
        sources=source_hashes, students=students, submission_semantics='every-available-worker-v1',
        training_steps=0, reserved_opened=args.phase == 'reserved', selection=selection,
        selection_sha256=selection_digest, wall_s=time.time()-started,
        runtime=dict(python=platform.python_version(), numpy=np.__version__,
                     torch=torch.__version__, numba=numba.__version__))
    (output/'complete.json').write_text(json.dumps(complete, indent=2)+'\n')


if __name__ == '__main__':
    main()
