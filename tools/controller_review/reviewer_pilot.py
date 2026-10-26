"""Fresh development diagnostic of archived residual PPO, not causal validation."""
import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
REV = ROOT / 'integrations/webots/research/revision9'
sys.path.insert(0, str(REV))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    # Set limits before numerical libraries are imported.
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    import numpy as np
    import torch
    from evaluate9 import episode, load_checkpoint, configure_lqr, GAINS, P

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    protocol = dict(
        purpose='Archived residual PPO checkpoint diagnostic; no training or selection',
        noise_base=1046000000, pairs=[0, 1, 2], speeds=[20],
        paths=['dlc220', 'sine120'],
        scenarios=['nominal', 'latency20', 'latency100'],
        methods=['lqr', 'fixed_m004', 'fixed_p004', 'scratch_100k', 'finetune_100k'],
        episodes=90, gate='unchanged revision5 execution / legacy predictive gate',
        limits=['Historical 20-feature interface contains pending/forecast information.',
                'Not validation of corrected causal PPO; zeroing channels would be a distribution shift.',
                'Simulated service delays; not OS deadlines, native Webots, or hardware.',
                'Known paths; development noise only; no reserved evaluation accessed.',
                'No checkpoint, gate, threshold, or training selection from this pilot.'],
        metrics='Mean episode penalized lateral RMSE; survival; authority; steering rate; raw traces retained',
        next_gate='Causal PPO training interface and matched supervisor ablations must precede new performance claims.')
    # Written before any rollout; never revise this protocol based on outcomes.
    (args.output / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    sources = {}
    for folder in ('revision2', 'revision4', 'revision5', 'revision7', 'revision8', 'revision9'):
        for file in (REV.parent / folder).glob('*.py'):
            sources[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    sources[str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.output / 'source-hashes.json').write_text(json.dumps(sources, indent=2) + '\n')
    training = REV.parent.parent / 'results/revision9-finetuning/training'
    original_splits = dict(P['splits'])
    configure_lqr()
    gains = np.array([GAINS[v] for v in (15, 20, 25)])
    (args.output / 'traces').mkdir()
    rows = []
    hashes = {}

    class Positive:
        def predict(self, observation, deterministic=True):
            return np.array([.5], dtype=np.float32), None

    with (args.output / 'episodes.csv').open('w', newline='') as handle:
        writer = None
        for pair in protocol['pairs']:
            P['splits'] = original_splits
            models = {'fixed_p004': Positive()}
            for arm in ('scratch', 'finetune'):
                file = training / f'{arm}-{P["rl_seeds"][pair]}' / 'checkpoint-100000/policy.zip'
                hashes[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
                models[arm + '_100k'] = load_checkpoint(training, arm, pair, 100000)
            P['splits'] = dict(original_splits, dev=protocol['noise_base'])
            (args.output / 'model-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
            for speed, path, scenario, method in itertools.product(
                    protocol['speeds'], protocol['paths'], protocol['scenarios'], protocol['methods']):
                trace = args.output / 'traces' / f'{pair}-{speed}-{path}-{scenario}-{method}.csv.gz'
                row = episode(models.get(method), method, pair, speed, path, scenario, gains, 'dev', trace)
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=row.keys())
                    writer.writeheader()
                writer.writerow(row)
                handle.flush()
                rows.append(row)
                print(f'{len(rows)}/{protocol["episodes"]}: {pair} {path} {scenario} {method}', flush=True)
    assert len(rows) == protocol['episodes']
    reference = {tuple(r[k] for k in ('pair', 'speed', 'path', 'scenario')): r
                 for r in rows if r['method'] == 'lqr'}
    summary = {}
    for method in protocol['methods']:
        subset = [r for r in rows if r['method'] == method]
        baseline = [reference[tuple(r[k] for k in ('pair', 'speed', 'path', 'scenario'))] for r in subset]
        mean = float(np.mean([r['penalized_rmse'] for r in subset]))
        base = float(np.mean([r['penalized_rmse'] for r in baseline]))
        for r, b in zip(subset, baseline):
            if r['scenario'] == 'latency100':
                assert r['penalized_rmse'] == b['penalized_rmse'] and r['active_fraction'] == 0
        summary[method] = dict(episodes=len(subset), survived=sum(r['survived'] for r in subset),
                              mean_penalized_rmse_m=mean, improvement_vs_lqr_pct=100*(base-mean)/base)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (args.output / 'complete.json').write_text(json.dumps(dict(episodes=len(rows),
        limitations=protocol['limits'], no_training=True), indent=2) + '\n')


if __name__ == '__main__':
    main()
