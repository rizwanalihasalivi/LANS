"""Frozen gate ablation on fresh development noise; never opens reserved splits."""
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
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(RESEARCH / 'revision8'))
import bootstrap
import numpy as np
import torch
import numba
from comparison import configure_lqr
from core import GAINS
from kernels import initial_executor, lqr, measure, path_values
from plant import advance
from student import load
from teacher import features
from gate12 import execution_step12

P = json.loads((HERE / 'protocol.json').read_text())
G = json.loads((RESEARCH / 'revision6/protocol.json').read_text())
RESULTS = RESEARCH.parent / 'results'
SOURCE_FILES = [
    'revision12/protocol.json', 'revision12/run12.py', 'revision12/gate12.py',
    'revision12/report12.py', 'revision12/test_gate12.py', 'revision12/test_report12.py',
    'revision8/bootstrap.py', 'revision8/student.py', 'revision8/teacher.py',
    'revision8/protocol.json', 'revision7/kernels.py', 'revision7/bootstrap.py',
    'revision5/execution.py', 'revision5/bootstrap.py', 'revision2/gating.py',
    'revision2/plant.py', 'revision6/protocol.json', 'core.py', 'comparison.py',
    'comparison-protocol.json', 'protocol.json',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def student_hashes():
    return {
        str(seed): {
            name: sha(RESULTS / f'revision8-student/students/{seed}' / name)
            for name in ('student.pt', 'normalization.npz', 'complete.json')
        } for seed in P['student_seeds']
    }


def noise_id(repetition, speed, path_name, region):
    return (P['development_noise_base'] + repetition * 10000 + speed * 100
            + P['paths'].index(path_name) * 10 + P['scenarios'].index(region))


def episode(method, repetition, speed, path_name, region, model, gains, trace=None):
    case = G['scenarios'][region]
    path = tuple(float(value) for value in G['paths'][path_name])
    scheduled = int(np.ceil((220 / speed + 2) / .01))
    identity = noise_id(repetition, speed, path_name, region)
    scales = np.array([.03, np.deg2rad(.17), .01, .1]) * case['noise']
    actual = np.random.default_rng(identity).normal(0, scales, (scheduled, 4))
    y, heading, _ = path_values(0., path)
    state = np.array([0., y + .15, heading + .01, 0., 0., 0.])
    estimate = np.zeros(4)
    cov = np.eye(4) * .01
    previous = np.zeros(4)
    worker = initial_executor()
    if method == 'lqr':
        variant, proposer = 0, 'lqr'
    else:
        variant_name, proposer = method.split('_', 1)
        variant = P['variants'][variant_name]
    errors, weights, rates, runtimes, records = [], [], [], [], []
    failed = False
    trajectory = hashlib.sha256()
    max_command = max_actuator = max_age = 0.
    submissions = 0
    for tick in range(scheduled):
        raw_v = (max(5., previous[3]) if case['sensor_delay_steps'] and tick
                 else max(5., speed + actual[tick, 3]))
        estimate, cov, previous, v, k = measure(
            state, float(speed), path, actual[tick], case['sensor_delay_steps'],
            estimate, cov, previous, tick == 0, float(case['noise']))
        observed = features(state, estimate, raw_v, path, worker, tick, case['service_ticks'])
        previews = observed[6:9].astype(np.float64) * .02
        baseline, gain = lqr(estimate, v, k, gains)
        available = worker[7] < 0 or worker[6] <= tick * .01 + 1e-9
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
                    raise ValueError('finite normalized residual action required')
                proposal = .08 * float(np.clip(action[0], -1., 1.))
        if method == 'lqr':
            command, weight, reason, submitted = baseline, 0., 10, False
        else:
            command, weight, reason, submitted = execution_step12(
                worker, tick * .01, proposal, case['service_ticks'], baseline,
                estimate, state[5], v, k, gain, previews, variant)
        runtimes.append(time.perf_counter() - started)
        submissions += int(submitted)
        if worker[3] >= 0:
            max_age = max(max_age, tick * .01 - worker[4])
        if region == 'latency100' and (command != baseline or weight != 0.):
            raise AssertionError('severe-delay exact LQR fallback violated')
        old_actuator = state[5]
        state = advance(state, command, float(speed), case['mu'], case['stiffness'])
        reference, heading, _ = path_values(state[0], path)
        error = state[1] - reference
        if not np.isfinite(state).all() or not np.isfinite(command):
            # Invalid physics is a run-integrity failure, never a fabricated finite score.
            raise FloatingPointError('nonfinite command/plant state')
        errors.append(error)
        weights.append(weight)
        rates.append(abs(state[5] - old_actuator) / .01)
        max_command = max(max_command, abs(command))
        max_actuator = max(max_actuator, abs(state[5]))
        trajectory.update(np.asarray([command, *state], dtype='<f8').tobytes())
        if trace is not None:
            records.append(dict(
                tick=tick, state_time_s=(tick + 1) * .01, x=state[0], y=state[1],
                heading=state[2], reference=reference, error=error, command=command,
                baseline=baseline, actuator=state[5], weight=weight, reason=reason,
                proposal=proposal, submitted=submitted, packet_sequence=worker[3],
                observed_s=worker[4] if worker[3] >= 0 else '',
                age_s=tick * .01-worker[4] if worker[3] >= 0 else '',
                pending_sequence=worker[7], **{f'obs{i}': observed[i] for i in range(20)}))
        if abs(error) > 2.5 or abs(state[2] - heading) > .6:
            failed = True
            break
    if max(rates) > .3500001 or max_command > .5000001 or max_actuator > .5000001:
        raise AssertionError('physical bounds violated')
    if trace is not None:
        with gzip.open(trace, 'wt', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=records[0], lineterminator='\n')
            writer.writeheader()
            writer.writerows(records)
    return dict(
        repetition=repetition, seed=P['student_seeds'][repetition], noise_id=identity,
        speed=speed, path=path_name, scenario=region, method=method,
        survived=not failed, steps=len(errors), scheduled_steps=scheduled,
        rmse=float(np.sqrt(np.mean(np.square(errors)))),
        penalized_rmse=float(np.sqrt((sum(x*x for x in errors)+(scheduled-len(errors))*6.25)/scheduled)),
        active_fraction=float(np.mean(np.array(weights) > 0)), mean_weight=float(np.mean(weights)),
        max_rate=max(rates), max_command=max_command, max_actuator=max_actuator,
        trajectory_sha256=trajectory.hexdigest(), wall_p99_s=float(np.quantile(runtimes, .99)),
        submissions=submissions, max_packet_age_s=max_age)


def shard(repetition, output):
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
        for speed, path_name, region in itertools.product(P['speeds'], P['paths'], P['scenarios']):
            for method in P['methods']:
                trace = (output / 'traces' / f'{region}-{method}.csv.gz'
                         if repetition == 0 and speed == 25 and path_name == 'dlc220' else None)
                row = episode(method, repetition, speed, path_name, region, model, gains, trace)
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=row, lineterminator='\n')
                    writer.writeheader()
                writer.writerow(row)
                handle.flush()
                count += 1
            print(repetition, speed, path_name, region, count, flush=True)
    assert count == 360
    (output / 'complete.json').write_text(json.dumps(dict(episodes=count, repetition=repetition))+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetition', type=int, choices=P['repetitions'])
    args = parser.parse_args()
    output = args.output.resolve()
    if args.repetition is not None:
        shard(args.repetition, output)
        return
    tracked_sources = [str((RESEARCH / name).relative_to(ROOT)) for name in SOURCE_FILES]
    subprocess.run(['git', 'ls-files', '--error-unmatch', '--', *tracked_sources],
                   cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', str(RESEARCH)], cwd=ROOT, check=True)
    source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    students = student_hashes()
    output.mkdir(parents=True, exist_ok=False)
    sources = {}
    for name in SOURCE_FILES:
        source = RESEARCH / name
        destination = output / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        sources[name] = sha(source)
    started = time.time()

    def job(repetition):
        env = os.environ.copy()
        env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        destination = output / f'pair-{repetition}'
        with (output / f'pair-{repetition}.log').open('w') as log:
            subprocess.run([sys.executable, str(HERE / 'run12.py'), '--output', str(destination),
                            '--repetition', str(repetition)], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        with (destination / 'episodes.csv').open() as handle:
            return list(csv.DictReader(handle))

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = [row for part in pool.map(job, P['repetitions']) for row in part]
    assert len(rows) == P['development_episodes']
    assert students == student_hashes(), 'student artifacts changed during run'
    assert all(sha(RESEARCH / name) == digest for name, digest in sources.items()), 'source changed during run'
    with (output / 'episodes.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    manifest = dict(
        episodes=len(rows), protocol=P, source_commit=source_commit, sources=sources, students=students,
        submission_semantics='every-available-worker-v1', split='development', training_steps=0,
        reserved_split_opened=False, wall_s=time.time()-started,
        runtime=dict(python=platform.python_version(), numpy=np.__version__, torch=torch.__version__, numba=numba.__version__))
    (output / 'complete.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
