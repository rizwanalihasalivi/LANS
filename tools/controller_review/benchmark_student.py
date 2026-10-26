"""Actual retained-student CPU timing on a deterministic closed-loop workload.
Not a tracking evaluation, native worker benchmark, or hardware deadline guarantee.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'integrations/webots/research/revision8'))
import numpy as np
import torch
from student import load
from teacher import features
from data import G
from kernels import measure, lqr, execution_step, path_values, initial_executor
from plant import advance
from comparison import configure_lqr
from core import GAINS


def summary(values):
    a = np.asarray(values) / 1e6
    return dict(samples=len(a), median_ms=float(np.median(a)),
                p95_ms=float(np.quantile(a, .95)), p99_ms=float(np.quantile(a, .99)),
                max_ms=float(a.max()), above_10ms=int((a >= 10).sum()),
                above_50ms=int((a >= 50).sum()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=2000)
    parser.add_argument('--warmup', type=int, default=200)
    args = parser.parse_args()
    if args.ticks < 100 or args.warmup < 1:
        parser.error('use at least 100 measured ticks and one warmup tick')
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    configure_lqr()
    gains = np.array([GAINS[v] for v in (15, 20, 25)])
    path = tuple(float(v) for v in G['paths']['dlc220'])
    rows, models = [], []
    for seed in (701, 802, 903):
        folder = ROOT / f'integrations/webots/results/revision8-student/students/{seed}'
        model = load(folder)
        models.append(dict(seed=seed, sha256=hashlib.sha256((folder/'student.pt').read_bytes()).hexdigest()))
        for service in (0, 2, 10):
            y, h, _ = path_values(0., path)
            state = np.array([0., y+.15, h+.01, 0., 0., 0.])
            estimate = np.zeros(4); cov = np.eye(4)*.01; previous = np.zeros(4)
            worker = initial_executor()
            for tick in range(args.warmup + args.ticks):
                # Deterministic nominal plant workload: no claim of fresh evaluation.
                estimate, cov, previous, v, k = measure(state, 20., path, np.zeros(4), 0,
                    estimate, cov, previous, tick == 0, 0.)
                start = time.perf_counter_ns()
                obs = features(state, estimate, 20., path, worker, tick, service)
                built = time.perf_counter_ns()
                baseline, gain = lqr(estimate, v, k, gains)
                base_done = time.perf_counter_ns()
                available = worker[7] < 0 or worker[6] <= tick*.01 + 1e-9
                proposal = 0.
                if available:
                    action, _ = model.predict(obs, deterministic=True)
                    proposal = .08*float(np.clip(action[0], -1., 1.))
                inferred = time.perf_counter_ns()
                command, weight, reason, submitted = execution_step(worker, tick*.01,
                    proposal, service, baseline, estimate, state[5], v, k, gain, False)
                finished = time.perf_counter_ns()
                if tick >= args.warmup:
                    rows.append(dict(seed=seed, simulated_service_ms=service*10, tick=tick,
                        policy_called=bool(available), observation_ns=built-start,
                        lqr_ns=base_done-built, policy_stage_ns=inferred-base_done,
                        execution_gate_ns=finished-inferred, total_ns=finished-start,
                        weight=float(weight), reason=int(reason)))
                state = advance(state, command, 20., 1., 1.)
                if not np.isfinite(state).all():
                    raise RuntimeError('nonfinite workload state')
    with (args.output/'samples.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    groups=[]
    for service in (0, 20, 100):
        subset=[r for r in rows if r['simulated_service_ms']==service]
        stages={key:summary([r[key] for r in subset]) for key in
                ('observation_ns','lqr_ns','execution_gate_ns','total_ns')}
        stages['policy_called_ns']=summary([r['policy_stage_ns'] for r in subset if r['policy_called']])
        groups.append(dict(simulated_service_ms=service, stages=stages))
    result=dict(kind='warm synchronous CPU wall-time microbenchmark of retained student and execution kernel',
        limitations=['single deterministic nominal DLC workload at 20 m/s; not a tracking comparison',
            'excludes sensor/observer, IPC, queueing, scheduler guarantees and physical actuator delay',
            'simulated service delay does not sleep the CPU and is not measured inference time',
            'warmup excludes model loading and Numba compilation; max is an observed sample, not WCET',
            'shared cloud CPU results do not establish native Webots or vehicle hardware deadlines'],
        platform=platform.platform(),cpu=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),platform.processor()),
        python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,
        threads=torch.get_num_threads(),affinity_cpus=len(os.sched_getaffinity(0)),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ticks_per_case=args.ticks,warmup_per_case=args.warmup,models=models,groups=groups)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(groups,indent=2))

if __name__ == '__main__':
    main()
