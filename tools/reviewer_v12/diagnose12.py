"""Descriptive audit of frozen v11 inputs/decisions; never selects reserved data."""
import boot12
from collections import Counter
import csv
import hashlib
import json
import math
import statistics
import numpy as np
from study11 import logits


def main(out):
    prior = boot12.ROOT/'docs/research/reviewer-training-v11'
    seal = json.loads((prior/'evidence-hashes.json').read_text())['sha256']
    for name, digest in seal.items():
        assert hashlib.sha256((prior/name).read_bytes()).hexdigest() == digest, name
    rows = list(csv.DictReader((prior/'episodes.csv').open()))
    selected = [r for r in rows if r['source'] == 'newppo_rk']
    scenarios = {}
    marginal = Counter()
    probs = []
    saturated = [[], []]
    counts = Counter()
    sse_windows = Counter()
    gradient_history = []
    for pair, seed in enumerate((701, 802, 903)):
        with np.load(prior/f'actors/newppo_rk-{seed}.npz', allow_pickle=False) as f:
            model = {k: f[k].copy() for k in f.files}
        pair_rows = [r for r in selected if int(r['pair']) == pair]
        for row in pair_rows:
            with np.load(prior/f'pair-{pair}/traces'/row['trace'], allow_pickle=False) as d:
                scenario = row['scenario']
                item = scenarios.setdefault(scenario, dict(ticks=0, issued=0, active=0, reasons=Counter(),
                    weight_sum=0., abs_correction_sum=0., actions=Counter(), advantage_eligible_packets=0))
                n = len(d['command'])
                issued = d['submitted'].astype(bool)
                item['ticks'] += n
                item['issued'] += int(issued.sum())
                item['active'] += int(np.count_nonzero(d['weight']))
                item['weight_sum'] += float(d['weight'].sum())
                item['abs_correction_sum'] += float(np.abs(d['command']-d['baseline']).sum())
                item['reasons'].update(d['reason'].tolist())
                item['actions'].update(map(str, d['proposed_residual'][issued].tolist()))
                counts['ticks'] += n
                counts['submitted'] += int(issued.sum())
                counts['active'] += int(np.count_nonzero(d['weight']))
                # Use the production single-row inference shape at class ties.
                x = d['query'][issued]
                logit = np.concatenate([logits(model, xx[None, :]) for xx in x])
                p = np.exp(logit-logit.max(1)[:, None]); p /= p.sum(1)[:, None]
                probs.append(p)
                marginal.update(p.argmax(1).tolist())
                h0 = np.tanh((x-model['mean'])/model['std']@model['w0']+model['b0'])
                h1 = np.tanh(h0@model['w1']+model['b1'])
                saturated[0].extend(np.mean(np.abs(h0) > .99, axis=1).tolist())
                saturated[1].extend(np.mean(np.abs(h1) > .99, axis=1).tolist())
                sse = d['lateral_error']**2
                sse_windows['total'] += float(sse.sum())
                sse_windows['first_second'] += float(sse[:100].sum())
                sse_windows['inactive'] += float(sse[d['weight'] == 0].sum())
        log = list(csv.DictReader((prior/f'training-{pair}/progress.csv').open()))
        gradient_history.append(dict(pair=pair, last={k: v for k, v in log[-1].items() if k.startswith('train/')}))
    p = np.concatenate(probs)
    for key, item in scenarios.items():
        a = [r for r in selected if r['scenario'] == key]
        b = [r for r in rows if r['source'] == 'lqr' and r['scenario'] == key]
        item['gain_vs_lqr_pct'] = 100*(1-statistics.mean(float(r['rmse_m']) for r in a)/statistics.mean(float(r['rmse_m']) for r in b))
        item['active_pct'] = 100*item['active']/item['ticks']
        item['mean_weight'] = item['weight_sum']/item['ticks']
        item['mean_abs_correction_rad'] = item['abs_correction_sum']/item['ticks']
    alpha = 1-math.exp(-.01/.3)
    result = dict(scope='All 120 frozen v11 new-PPO episodes; descriptive associations, not independent causes',
        prior_seal_sha256=hashlib.sha256((prior/'evidence-hashes.json').read_bytes()).hexdigest(), counts=dict(counts),
        scenarios=scenarios, deterministic_action_histogram=dict(marginal),
        mean_entropy_nats=float(np.mean(-np.sum(p*np.log(np.maximum(p, 1e-30)), axis=1))),
        max_entropy_nats=math.log(5), mean_max_action_probability=float(p.max(1).mean()),
        fraction_max_probability_over_099=float(np.mean(p.max(1) > .99)),
        tanh_saturation_fraction=[statistics.mean(x) for x in saturated],
        error_energy=dict(sse_windows),
        analytic_authority=dict(maximum_residual_rad=.08, cap=.25, maximum_correction_rad=.02,
            recovery_weight=.05, filter_alpha=alpha, first_fresh_tick_from_zero_filter_rad=.05*alpha*.08,
            stale_cutoff_s=.05, assistance_ticks_for_arrival_10_20_40_100_ms=[4, 3, 1, 0],
            note='First-tick magnitude is a ceiling if recovery already qualifies; startup recovery itself commands zero.'),
        credit=dict(gamma=.99, gae_lambda=.95,
            td_residual_gae_coeff_after_10_20_40_100_ticks=[(.99*.95)**n for n in (10, 20, 40, 100)],
            note='GAE discounts TD residuals; these coefficients are not a measured policy-effect fraction or proof that lambda is the cause.'),
        optimizer_last_logs=gradient_history,
        findings=['The baseline remains the full LQR command; PPO proposes a bounded residual, not full-command driving.',
                  'The accepted actuator correction is weight times filtered residual. Mean weight is not percent driving contribution.',
                  'At 100ms the 50ms freshness contract forces exact LQR fallback. These scenarios cannot show learned tracking improvement.',
                  'Cost rejection and recovery can remove actor authority even when an action was submitted and receives policy-gradient credit.',
                  'Fixed discrete proposal magnitudes, smoothing/recovery and a strong feedback baseline restrict useful action effects.',
                  'Continued training began from a low-entropy inherited policy. This is an exploration limitation, not proof of a code defect.',
                  'The existing reward already includes executed lateral/heading/actuator-rate/steering cost; no latency reward under action control is assumed.'])
    (out/'diagnosis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('counts', 'mean_entropy_nats', 'fraction_max_probability_over_099', 'tanh_saturation_fraction')}))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--output', type=boot12.Path, required=True)
    main(p.parse_args().output)
