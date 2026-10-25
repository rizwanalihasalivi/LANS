"""Descriptive tables from paired episode records, never placeholder results."""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


def summarize(path):
    with Path(path).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('episode CSV is empty')
    fields = rows[0]
    metric = next((k for k in ('penalized_rmse', 'failure_penalized_rmse_m',
                              'penalized_rmse_m') if k in fields), None)
    if metric is None or not {'seed', 'method', 'survived'} <= fields.keys():
        raise ValueError('require seed, method, survived and a failure-penalized RMSE column')
    conditions = [k for k in ('seed', 'noise_seed', 'noise_id', 'speed', 'speed_m_s', 'path',
                              'scenario', 'delay_ms', 'service_ticks', 'randomize', 'config_index') if k in fields]
    if 'scheduled_steps' in fields and ('steps' not in fields or not ({'rmse', 'rmse_m'} & fields.keys())):
        raise ValueError('scheduled horizon requires executed steps and raw RMSE for penalty validation')
    paired = defaultdict(set)
    groups = defaultdict(list)
    for row in rows:
        value = float(row[metric])
        if not math.isfinite(value) or value < 0 or row['survived'] not in ('True', 'False'):
            raise ValueError('finite nonnegative RMSE and explicit boolean survival required')
        key = tuple(row[k] for k in conditions)
        if key in paired[row['method']]:
            raise ValueError('duplicate method/condition record')
        paired[row['method']].add(key)
        if 'scheduled_steps' in fields:
            n, total = int(row['steps']), int(row['scheduled_steps'])
            if not 0 < n <= total or (row['survived'] == 'True' and n != total):
                raise ValueError('incomplete or invalid episode horizon')
            raw_key = 'rmse' if 'rmse' in fields else 'rmse_m'
            raw = float(row[raw_key])
            expected = math.sqrt((n*raw**2 + (total-n)*2.5**2)/total)
            if not math.isfinite(raw) or raw < 0 or not math.isclose(value, expected, abs_tol=1e-9, rel_tol=1e-9):
                raise ValueError('failure penalty disagrees with the recorded 2.5 m tail rule')
        region = row.get('scenario', 'all')
        delay = row.get('delay_ms', str(int(row['service_ticks'])*10) if 'service_ticks' in row else '')
        groups[(region, delay, row['method'])].append(row)
    if any(keys != next(iter(paired.values())) for keys in paired.values()):
        raise ValueError('methods do not have identical paired condition coverage')
    table = []
    for (region, delay, method), selected in sorted(groups.items()):
        seeds = defaultdict(list)
        for row in selected:
            seeds[row['seed']].append(float(row[metric]))
        if len({len(v) for v in seeds.values()}) != 1:
            raise ValueError('unequal condition counts across seeds')
        values = [mean(v) for v in seeds.values()]
        table.append(dict(scenario=region, delay_ms=delay, method=method,
                          episodes=len(selected), survived=sum(r['survived']=='True' for r in selected),
                          seeds=len(values), mean_episode_rmse_m=mean(values),
                          seed_mean_sd_m=stdev(values) if len(values)>1 else None))
    return table, metric


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='one paired episode CSV')
    parser.add_argument('--output', type=Path, required=True, help='new output directory')
    args = parser.parse_args()
    table, metric = summarize(args.input)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output/'summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=table[0], lineterminator='\n')
        writer.writeheader(); writer.writerows(table)
    lines = ['# Recorded method comparison', '', f'Source: `{args.input.resolve()}`',
             f'Metric: `{metric}`. Mean of episode RMSEs, equally aggregated across seed means.', '',
             'SD is across seed means, not time samples. Repeated deterministic seeds are not independent evidence.',
             'This table is descriptive; method labels alone do not establish causal ablations, significance or safety.', '',
             '| Scenario | Delay (ms) | Method | Survived / episodes | Seeds | Mean RMSE (m) | Seed-mean SD (m) |',
             '|---|---:|---|---:|---:|---:|---:|']
    for row in table:
        sd = 'unavailable (one seed)' if row['seed_mean_sd_m'] is None else f"{row['seed_mean_sd_m']:.6f}"
        lines.append(f"| {row['scenario']} | {row['delay_ms']} | {row['method']} | {row['survived']}/{row['episodes']} | {row['seeds']} | {row['mean_episode_rmse_m']:.6f} | {sd} |")
    (args.output/'report.md').write_text('\n'.join(lines)+'\n')
    (args.output/'source.json').write_text(json.dumps(dict(source=str(args.input.resolve()), metric=metric,
        purpose='descriptive paired comparison; no synthetic fallback'), indent=2)+'\n')
    print(args.output/'report.md')


if __name__ == '__main__':
    main()
