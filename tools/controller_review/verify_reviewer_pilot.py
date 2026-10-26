"""Recompute archived pilot metrics and exact severe-delay paired trajectories."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    run = args.run
    protocol = json.loads((run / 'protocol.json').read_text())
    with (run / 'episodes.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    fields = ('pair', 'speed', 'path', 'scenario', 'method')
    keys = [tuple(r[k] for k in fields) for r in rows]
    expected = {tuple(map(str, k)) for k in itertools.product(protocol['pairs'], protocol['speeds'],
                protocol['paths'], protocol['scenarios'], protocol['methods'])}
    assert len(keys) == len(set(keys)) == protocol['episodes'] and set(keys) == expected
    for name in ('source-hashes.json', 'model-hashes.json'):
        for relative, digest in json.loads((run / name).read_text()).items():
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest, relative
    audited = {}
    metrics = []
    for row, key in zip(rows, keys):
        file = run / 'traces' / ('-'.join(key) + '.csv.gz')
        with gzip.open(file, 'rt') as handle:
            trace = list(csv.DictReader(handle))
        scheduled = int(row['scheduled_steps'])
        assert len(trace) == int(row['steps'])
        score = ((sum(float(r['error']) ** 2 for r in trace) +
                  (scheduled - len(trace)) * 6.25) / scheduled) ** .5
        assert abs(score - float(row['penalized_rmse'])) < 1e-12
        for r in trace:
            assert abs(float(r['command'])) <= .5000001
        angles = [0.] + [float(r['actuator']) for r in trace]
        changes = [b-a for a, b in zip(angles, angles[1:])]
        assert max(map(abs, changes)) <= .003500001
        # obs1 is an estimator output, NOT ground-truth heading error.
        metrics.append(dict(zip(fields, key),
            penalized_lateral_rmse_m=score,
            estimated_heading_rmse_rad=math.sqrt(sum((float(r['obs1'])*.3)**2 for r in trace)/len(trace)),
            steering_rate_rms_rad_s=math.sqrt(sum((d/.01)**2 for d in changes)/len(changes)),
            total_steering_movement_rad=sum(map(abs, changes))))
        # Region order comes from the archived protocol, not assumed here.
        original = json.loads((root / 'integrations/webots/research/revision6/protocol.json').read_text())
        noise = (protocol['noise_base'] + int(row['pair']) * 10000 + int(row['speed']) * 100 +
                 list(original['paths']).index(row['path']) * 10 + list(original['scenarios']).index(row['scenario']))
        assert int(row['noise_id']) == noise
        audited[key] = trace
    severe = 0
    for key, trace in audited.items():
        if key[3] != 'latency100' or key[4] == 'lqr':
            continue
        base = audited[key[:-1] + ('lqr',)]
        assert len(base) == len(trace)
        for a, b in zip(trace, base):
            assert float(a['weight']) == 0
            for field in ('x', 'y', 'reference', 'error', 'command', 'baseline', 'actuator'):
                assert a[field] == b[field], (key, field)
        severe += 1
    result = dict(episodes=len(rows), exact_severe_delay_pairs=severe,
                  raw_metrics_recomputed=True, source_and_model_hashes_verified=True,
                  scope='Historical simulated-service diagnostic only; no causal deployment or real-time claim')
    (run / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    with (run / 'independent-metrics.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=metrics[0].keys())
        writer.writeheader()
        writer.writerows(metrics)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
