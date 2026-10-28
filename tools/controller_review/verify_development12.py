"""Single-row actor/planner replay, independent aggregate metrics and strict target."""
# Corrected verification entry preserves the frozen experiment and original failed verifier.
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/reviewer_v12'))
import boot12
import csv
import itertools
import json
import math
import statistics
import numpy as np
from study12 import P, FIELDS, make_env, residual_for, models_for
from checkpoint12 import atomic_json, digest


def equal_typed(value, recorded):
    if isinstance(value, (bool, np.bool_)):
        return isinstance(recorded, (bool, np.bool_)) and bool(value) == bool(recorded)
    if isinstance(value, (int, np.integer)):
        return isinstance(recorded, (int, np.integer)) and int(value) == int(recorded)
    return (math.isnan(value) and math.isnan(recorded)) or abs(float(value)-float(recorded)) <= 1e-11


def main(run):
    rows = []; ticks = queries = exact = 0; cfg = P['development']
    for pair in range(3):
        rr = list(csv.DictReader((run/f'pair-{pair}/episodes.csv').open()))
        keys = {(int(r['speed']), r['path'], int(r['mirror']), r['scenario'], r['source']) for r in rr}
        expected = set(itertools.product(cfg['speeds'], cfg['paths'], cfg['mirrors'], cfg['scenarios'], cfg['sources']))
        assert len(rr) == len(keys) == 400 and keys == expected
        models = models_for(run, pair)
        for row in rr:
            file = run/f'pair-{pair}/traces'/row['trace']
            assert digest(file) == row['trace_sha256']
            with np.load(file, allow_pickle=False) as f:
                d = {k: f[k].copy() for k in f.files}
            source = row['source']; scenario = row['scenario']; n = len(d['command'])
            case = (int(row['speed']), row['path'], int(row['mirror']), 'tire' if scenario == 'tire' else 'nominal', int(row['noise_id']))
            env = make_env(case, source, scenario); env.reset()
            for tick in range(n):
                np.testing.assert_array_equal(env.raw, d['raw'][tick])
                if env.ctrl.pending is None:
                    np.testing.assert_array_equal(env.obs, d['query'][tick])
                    history = [env.query_meta[k] for k in ('estimated_delay_s', 'used_horizon_s', 'completed_history_samples', 'last_completed_sequence')]
                    np.testing.assert_array_equal(history, d['forecast_history'][tick])
                    if source in models: queries += 1
                else:
                    assert np.isnan(d['query'][tick]).all()
                residual = residual_for(env, source, models.get(source))
                assert abs(residual-d['proposed_residual'][tick]) < 1e-12
                _, _, failed, done, checked = env.step_residual(residual)
                assert checked['reason'] == d['reason'][tick]
                for key in FIELDS:
                    value = math.nan if checked[key] is None else checked[key]
                    recorded = d[key][tick]
                    assert equal_typed(value, recorded), (row['trace'], tick, key)
                assert not (failed or done) or tick == n-1
            assert env.tick == int(row['steps']) == n
            assert env.horizon == int(row['scheduled'])
            assert (not failed) == (row['survived'] == 'True') and (done or failed)
            assert np.max(np.abs(d['command'])) <= .5000001
            assert np.max(np.abs(d['steering_rate'])) <= .3500001
            active = d['weight'] > 0
            assert np.all((d['packet_age_s'][active] >= 0) & (d['packet_age_s'][active] < .05))
            h = env.horizon
            metrics = dict(rmse_m=math.sqrt((float(d['lateral_error']@d['lateral_error'])+(h-n)*6.25)/h),
                heading_rmse_rad=math.sqrt(float(d['heading_error']@d['heading_error'])/n),
                rate_rms_rad_s=math.sqrt(float(d['steering_rate']@d['steering_rate'])/n),
                movement_rad=float(np.abs(d['steering_rate']).sum()*.01))
            for name, value in metrics.items(): assert abs(value-float(row[name])) < 1e-11
            assert int(row['active_ticks']) == int(active.sum())
            if scenario == 'delay100' and source != 'lqr':
                baseline = file.with_name(row['trace'].replace('-'+source+'.npz', '-lqr.npz'))
                with np.load(baseline, allow_pickle=False) as b:
                    for key in ('command', 'x', 'y', 'heading', 'actuator'): np.testing.assert_array_equal(d[key], b[key])
                exact += 1
            ticks += n
        rows += rr
        print('Verified', pair, len(rows), ticks, queries, flush=True)
    mean = lambda group, metric: statistics.mean(float(r[metric]) for r in group)
    summary = {}
    for source in cfg['sources']:
        group = [r for r in rows if r['source'] == source]
        summary[source] = {k: mean(group, k) for k in ('rmse_m', 'heading_rmse_rad', 'rate_rms_rad_s', 'movement_rad')}
        summary[source].update(episodes=len(group), survived=sum(r['survived'] == 'True' for r in group),
                               active_ticks=sum(int(r['active_ticks']) for r in group))
    base = summary['lqr']
    for stats in summary.values(): stats['gain_vs_lqr_pct'] = 100*(1-stats['rmse_m']/base['rmse_m'])
    targets = {}
    for arm in P['training']['arms']:
        reasons = []; gains = {}; pair_gains = {}
        for ref in ('lqr', 'negative', 'positive', 'student', 'oldppo', 'prior', 'planner'):
            gains[ref] = 100*(1-summary[arm]['rmse_m']/summary[ref]['rmse_m'])
            if summary[arm]['rmse_m'] > .8*summary[ref]['rmse_m']: reasons.append('less_than20pct_vs_'+ref)
            pair_gains[ref] = []
            for pair in range(3):
                aa = [r for r in rows if int(r['pair']) == pair and r['source'] == arm]
                bb = [r for r in rows if int(r['pair']) == pair and r['source'] == ref]
                gain = 100*(1-mean(aa, 'rmse_m')/mean(bb, 'rmse_m')); pair_gains[ref].append(gain)
                if gain <= 0: reasons.append(f'nonpositive_pair{pair}_vs_{ref}')
        for metric in ('heading_rmse_rad', 'rate_rms_rad_s'):
            if summary[arm][metric] > 1.05*base[metric]: reasons.append('more_than5pct_'+metric)
        aa = [r for r in rows if r['source'] == arm and r['scenario'] == 'nominal']
        bb = [r for r in rows if r['source'] == 'lqr' and r['scenario'] == 'nominal']
        if mean(aa, 'rmse_m') > 1.02*mean(bb, 'rmse_m'): reasons.append('nominal_more_than2pct_worse')
        if summary[arm]['survived'] != summary[arm]['episodes']: reasons.append('survival_loss')
        targets[arm] = dict(twenty_percent_pass=not reasons, gains_pct=gains, pair_gains_pct=pair_gains, reasons=reasons)
    for name, expected in json.loads((run/'manifest.json').read_text())['inputs'].items():
        assert digest(boot12.ROOT/name) == expected, name
    for name, expected in json.loads((run/'actors/manifest.json').read_text())['sha256'].items():
        assert digest(run/'actors'/name) == expected, name
    result = dict(episodes=len(rows), transitions=ticks, neural_queries=queries, exact_delay100_pairs=exact,
        full_replay=True, arms=targets, promoted=False, reserved='unopened', missing_published_vehicle_baselines=True,
        scope='Independent metrics and deterministic code replay; not an independent simulator or physical validation')
    atomic_json(run/'decision.json', result); atomic_json(run/'summary.json', summary)
    with (run/'episodes.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__": main(ROOT/"docs/research/ppo-audit-v12")
