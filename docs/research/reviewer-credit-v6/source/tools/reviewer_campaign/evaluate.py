"""Matched mirrored development grid; full true heading and actuator metrics."""
import common
import argparse
import csv
import gzip
import itertools
import json
import math
import time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from supervisor import P
from environment import CausalEnv
from train import student_folder
from causal_student import load_causal


def run_episode(model, method, pair, speed, path, sign, scenario, noise_id, trace):
    mode = {'lqr':'lqr', 'fixed_authority':'fixed', 'latency_gain':'latency',
            'no_recovery':'no_recovery'}.get(method, 'predictive')
    env = CausalEnv(pair=pair, mode=mode, case=(speed,path,sign,scenario,noise_id))
    obs, _ = env.reset()
    rows = []
    inferred = []
    processed = []
    reasons = {}
    while True:
        started = time.perf_counter_ns()
        residual = 0.
        infer_ns = 0
        if env.ctrl.pending is None:
            if method == 'fixed_negative':
                residual = -.04
            elif method == 'fixed_positive':
                residual = .04
            elif method != 'lqr':
                begin = time.perf_counter_ns()
                a, _ = model.predict(obs, deterministic=True)
                infer_ns = time.perf_counter_ns()-begin
                # Student returns normalized residual; PPO returns class index.
                residual = .08*float(a[0]) if method == 'student' else P['candidates_rad'][int(a)]
                inferred.append(infer_ns)
        obs, _, failed, done, info = env.step_residual(residual)
        elapsed = time.perf_counter_ns()-started
        processed.append(elapsed)
        info['inference_ns'] = infer_ns
        info['processing_ns'] = elapsed
        reasons[info['reason']] = reasons.get(info['reason'], 0)+1
        rows.append(info)
        if failed or done:
            break
    with gzip.open(trace, 'wt', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    n = env.horizon
    penalized = math.sqrt((sum(r['lateral_error']**2 for r in rows)+(n-len(rows))*6.25)/n)
    return dict(pair=pair, seed=P['seeds'][pair], speed=speed, path=path, mirror=sign,
        scenario=scenario, method=method, noise_id=noise_id, steps=len(rows), scheduled=n,
        survived=not failed, penalized_lateral_rmse_m=penalized,
        lateral_rmse_m=math.sqrt(sum(r['lateral_error']**2 for r in rows)/len(rows)),
        heading_rmse_rad=math.sqrt(sum(r['heading_error']**2 for r in rows)/len(rows)),
        max_lateral_error_m=max(abs(r['lateral_error']) for r in rows),
        steering_rate_rms_rad_s=math.sqrt(sum(r['steering_rate']**2 for r in rows)/len(rows)),
        total_steering_movement_rad=sum(abs(r['steering_rate'])*.01 for r in rows),
        active_fraction=sum(r['weight']>0 for r in rows)/len(rows),
        inference_p99_ns=float(np.quantile(inferred,.99)) if inferred else None,
        processing_p99_ns=float(np.quantile(processed,.99)),
        reasons=json.dumps(reasons, sort_keys=True))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--training', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pair', type=int, choices=range(3), required=True)
    p.add_argument('--grid', choices=['smoke', 'development', 'confirmation'], default='development')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'traces').mkdir()
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    pair = args.pair
    models = {'student':load_causal(student_folder(pair))}
    for arm in P['arms']:
        folder = args.training/f'{arm}-{P["seeds"][pair]}'
        assert json.loads((folder/'complete.json').read_text())['protocol'] == P
        models[arm] = PPO.load(folder/'policy.zip', device='cpu')
    for method in ('fixed_authority', 'latency_gain', 'no_recovery'):
        models[method] = models['finetune']
    grid = dict(P['development']) if args.grid == 'confirmation' else P[args.grid]
    if args.grid == 'confirmation':
        grid['paths'] = ['heldout_sine145']
        manifest = args.output.parent.parent/'confirmation-manifest.json'
        if not manifest.exists():
            raise ValueError('frozen confirmation manifest required')
    rows = []
    cells = list(itertools.product(grid['speeds'], grid['paths'], grid['mirrors'], grid['scenarios']))
    with (args.output/'episodes.csv').open('w', newline='') as handle:
        writer = None
        for cell_index, (speed, path, sign, scenario) in enumerate(cells):
            # Mirrors share canonical noise, initial state and disturbance signs.
            noise_id = (P['confirmation_noise_base'] if args.grid == 'confirmation' else P['development_noise_base'])
            noise_id += (pair*100000+speed*1000+
                        list(grid['paths']).index(path)*100+list(grid['scenarios']).index(scenario)*10)
            for method in grid['methods']:
                name = f'{speed}-{path}-{sign}-{scenario}-{method}'
                row = run_episode(models.get(method), method, pair, speed,path,sign,scenario,
                                  noise_id,args.output/'traces'/f'{name}.csv.gz')
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=row.keys(), lineterminator='\n')
                    writer.writeheader()
                writer.writerow(row); handle.flush(); rows.append(row)
            print(f'{args.grid} pair={pair} cells={cell_index+1}/{len(cells)}', flush=True)
    (args.output/'complete.json').write_text(json.dumps(dict(grid=args.grid,pair=pair,
        episodes=len(rows), protocol=P),indent=2)+'\n')


if __name__ == '__main__':
    main()
