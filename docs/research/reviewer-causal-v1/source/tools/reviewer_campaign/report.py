"""Independent episode/trace audit, paired summaries and conservative promotion."""
import common
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path
from supervisor import P


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--grid', choices=['smoke','development','confirmation'], default='development')
    args = p.parse_args()
    folder = args.run/args.grid
    grid = dict(P['development']) if args.grid == 'confirmation' else P[args.grid]
    if args.grid == 'confirmation':
        grid['paths'] = ['heldout_sine145']
    rows = []
    severe = 0
    for pair in range(3):
        shard = folder/f'pair-{pair}'
        with (shard/'episodes.csv').open() as handle:
            batch = list(csv.DictReader(handle))
        expected = set(itertools.product(grid['speeds'], grid['paths'], grid['mirrors'], grid['scenarios'], grid['methods']))
        keys = [(int(r['speed']),r['path'],int(r['mirror']),r['scenario'],r['method']) for r in batch]
        assert len(keys) == len(set(keys)) == len(expected) and set(keys) == expected
        lookup = dict(zip(keys,batch))
        def trace_for(key):
            with gzip.open(shard/'traces'/('-'.join(map(str,key))+'.csv.gz'), 'rt') as handle:
                return list(csv.DictReader(handle))
        for row, key in zip(batch,keys):
            trace = trace_for(key)
            n = int(row['scheduled'])
            assert len(trace) == int(row['steps'])
            rmse = math.sqrt((sum(float(r['lateral_error'])**2 for r in trace)+(n-len(trace))*6.25)/n)
            heading = math.sqrt(sum(float(r['heading_error'])**2 for r in trace)/len(trace))
            rate = math.sqrt(sum(float(r['steering_rate'])**2 for r in trace)/len(trace))
            assert abs(rmse-float(row['penalized_lateral_rmse_m'])) < 1e-12
            assert abs(heading-float(row['heading_rmse_rad'])) < 1e-12
            assert abs(rate-float(row['steering_rate_rms_rad_s'])) < 1e-12
            for r in trace:
                assert abs(float(r['command'])) <= .5000001
                assert abs(float(r['steering_rate'])) <= .3500001
                assert all(float(r[f'obs{i}']) == 0 for i in (14,15,16,17,19))
                if float(r['weight']) > 0:
                    assert r['packet_age_s'] and 0 <= float(r['packet_age_s']) < .05
                    command = max(-.5,min(.5,float(r['baseline'])+float(r['weight'])*float(r['packet_residual'])))
                    assert abs(command-float(r['command'])) < 1e-12
            if key[3] == 'delay100' and key[4] != 'lqr':
                base = trace_for(key[:-1]+('lqr',))
                assert len(trace) == len(base)
                for a,b in zip(trace,base):
                    assert float(a['weight']) == 0
                    assert all(a[k] == b[k] for k in ('x','y','heading','command','actuator'))
                severe += 1
        rows.extend(batch)
    mean = lambda subset,key: statistics.mean(float(r[key]) for r in subset)
    summary = {}
    base = [r for r in rows if r['method']=='lqr']
    for method in grid['methods']:
        subset = [r for r in rows if r['method']==method]
        value = mean(subset,'penalized_lateral_rmse_m')
        summary[method] = dict(episodes=len(subset),survived=sum(r['survived']=='True' for r in subset),
            rmse_m=value, gain_vs_lqr_pct=100*(mean(base,'penalized_lateral_rmse_m')-value)/mean(base,'penalized_lateral_rmse_m'),
            heading_rmse_rad=mean(subset,'heading_rmse_rad'), steering_rate_rms_rad_s=mean(subset,'steering_rate_rms_rad_s'),
            total_steering_movement_rad=mean(subset,'total_steering_movement_rad'))
    candidate = summary['finetune']
    reasons = []
    for method in ('lqr','student','fixed_negative','fixed_positive'):
        if candidate['rmse_m'] > .99*summary[method]['rmse_m']:
            reasons.append(f'finetune lacks >=1% improvement vs {method}')
        if candidate['survived'] < summary[method]['survived']:
            reasons.append(f'survival vs {method}')
    for pair in range(3):
        a = [r for r in rows if int(r['pair'])==pair and r['method']=='finetune']
        b = [r for r in rows if int(r['pair'])==pair and r['method']=='student']
        if mean(a,'penalized_lateral_rmse_m') >= mean(b,'penalized_lateral_rmse_m'):
            reasons.append(f'pair{pair} does not improve student')
    for key in ('heading_rmse_rad','steering_rate_rms_rad_s'):
        if candidate[key] > 1.05*summary['lqr'][key]:
            reasons.append(f'{key} exceeds 5% LQR tradeoff limit')
    a = [r for r in rows if r['method']=='finetune' and r['scenario']=='nominal']
    b = [r for r in rows if r['method']=='lqr' and r['scenario']=='nominal']
    if mean(a,'penalized_lateral_rmse_m') > 1.02*mean(b,'penalized_lateral_rmse_m'):
        reasons.append('nominal degradation >2% LQR')
    if args.grid == 'smoke':
        reasons.append('smoke grid cannot select or unlock confirmation')
    decision = dict(eligible=not reasons, reasons=reasons, grid=args.grid, episodes=len(rows),
        exact_severe_delay_pairs=severe, raw_metrics_verified=True,
        local_deadlines='NOT evaluated by simulated-service episodes',
        formal_safety='NOT established', physical_validation='NOT performed')
    (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (folder/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    with (folder/'episodes.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0].keys(),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    lines=[f'# Causal residual campaign: {args.grid}','',
        'All metrics below are simulated-service closed-loop measurements, not native or real-time guarantees. PPO has 25,000 additional steps per seed; supervised pretraining is extra.', '',
        '| Method | Penalized lateral RMSE (m) | Gain vs LQR | Heading RMSE (rad) | Steering-rate RMS (rad/s) | Survival |',
        '|---|---:|---:|---:|---:|---:|']
    for name,m in summary.items():
        lines.append(f'| {name} | {m["rmse_m"]:.6f} | {m["gain_vs_lqr_pct"]:.3f}% | {m["heading_rmse_rad"]:.6f} | {m["steering_rate_rms_rad_s"]:.6f} | {m["survived"]}/{m["episodes"]} |')
    lines+=['','## Decision','',f'Eligible: **{decision["eligible"]}**.']
    lines += [f'- {reason}' for reason in reasons]
    lines += ['',f'Independent raw-trace audit: {len(rows)} episodes, {severe} exact severe-delay LQR pairs.', '',
        'The latency-gain arm is a documented manuscript-inspired reconstruction, not an exact reproduction of a published algorithm. All simple-gain arms share stale rejection. No unknown future output or configured service delay enters the actor.', '',
        'No formal neuro-symbolic novelty, published-controller superiority, hard-real-time, GPU speedup, energy, or vehicle-readiness claim is supported by this grid. If eligibility fails, reserved confirmation remains unopened.']
    (folder/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(decision,indent=2))


if __name__ == '__main__':
    main()
