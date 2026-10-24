"""Verify complete v2 evidence and report every preregistered operating region."""
import csv,hashlib,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DEV=ROOT/'results/revision2-development'
TEST=ROOT/'results/revision2-test'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((DEV/'freeze.json').read_text());protocol=freeze['protocol']
assert sha(DEV/'episodes.csv')==freeze['development_csv_sha256']
start=json.loads((TEST/'start.json').read_text());complete=json.loads((TEST/'complete.json').read_text())
assert start['freeze_sha256']==sha(DEV/'freeze.json')
assert start['source_sha256']==complete['source_sha256']==freeze['source_sha256']
assert start['policy_sha256']==freeze['policy_sha256']
for name,digest in complete['source_sha256'].items():
    assert sha(TEST/'source'/name)==digest
    assert sha(HERE.parent/name)==digest
for name,digest in start['policy_sha256'].items():assert sha(ROOT/'results/research-training'/name/'policy.zip')==digest
assert complete['episodes_sha256']==sha(TEST/'episodes.csv')
with (TEST/'episodes.csv').open() as f:rows=list(csv.DictReader(f))
keys=[(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method']) for r in rows]
expected=set(itertools.product(protocol['test_policy_seeds'],protocol['test_speeds'],protocol['test_paths'],protocol['scenarios'],protocol['methods']))
assert len(keys)==len(set(keys))==len(expected)==complete['episodes'] and set(keys)==expected
for r in rows:
    assert float(r['max_rate'])<=.3500001
    assert int(r['steps'])<=int(r['scheduled_steps'])
    assert int(r['noise_seed'])>=protocol['reserved_test_noise_base']
    if r['survived']=='True':assert r['steps']==r['scheduled_steps']
    assert math.isfinite(float(r['penalized_rmse']))
    if r['scenario']=='latency100' and r['method'].startswith('gated'):assert float(r['active_fraction'])==0
    if r['method'].startswith('gated') and float(r['active_fraction'])==0:
        baseline=next(x for x in rows if x['method']=='lqr' and all(x[k]==r[k] for k in ['seed','speed','path','scenario']))
        assert r['penalized_rmse']==baseline['penalized_rmse']
lines=['# Performance-gated revision: reserved test results','',
       f"Verified {len(rows)} paired episodes. Reused frozen policies: five trained seeds; new reserved noise streams. Development selected `{freeze['selected_config']}`; acceptance constraints passed: **{freeze['development_accepted']}**.",'',
       'No training or gate tuning used these reserved results. All predeclared regions and methods appear below. Confidence intervals are descriptive, unadjusted across six regions; they are not a multiple-comparison significance claim.','',
       '| Region | Method | Survived / 30 | Mean penalized RMSE (m) | Mean active fraction | Mean weight |',
       '|---|---|---:|---:|---:|---:|']
for scenario,method in itertools.product(protocol['scenarios'],protocol['methods']):
    rs=[r for r in rows if r['scenario']==scenario and r['method']==method]
    lines.append(f"| {scenario} | {method} | {sum(r['survived']=='True' for r in rs)} | {mean(float(r['penalized_rmse']) for r in rs):.6f} | {mean(float(r['active_fraction']) for r in rs):.2%} | {mean(float(r['mean_weight']) for r in rs):.4f} |")
lines+=['','## Predeclared primary comparison: gated residual vs LQR','',
        'Each paired difference is aggregated over six conditions per trained seed before computing the mean, sample SD and t(4) interval. Negative differences favor the hybrid. The five policies are reused, not newly trained independent replicas.','',
        '| Region | RMSE change | Mean paired difference (m) | Seed SD (m) | Descriptive 95% interval (m) | Better seeds / 5 | Survival delta | Meets region criterion |',
        '|---|---:|---:|---:|---|---:|---:|---|']
comparisons={}
for scenario in protocol['scenarios']:
    selected=lambda method,seed:[r for r in rows if r['scenario']==scenario and r['method']==method and int(r['seed'])==seed]
    differences=[]
    for seed in protocol['test_policy_seeds']:
        differences.append(mean(float(r['penalized_rmse']) for r in selected('gated_residual',seed))-mean(float(r['penalized_rmse']) for r in selected('lqr',seed)))
    base=[r for r in rows if r['scenario']==scenario and r['method']=='lqr'];hybrid=[r for r in rows if r['scenario']==scenario and r['method']=='gated_residual']
    delta=mean(differences);sd=stdev(differences);ci=2.776445105*sd/math.sqrt(5)
    ratio=delta/mean(float(r['penalized_rmse']) for r in base)
    survival=sum(r['survived']=='True' for r in hybrid)-sum(r['survived']=='True' for r in base)
    wins=sum(d<0 for d in differences)
    qualifies=ratio<=-.05 and wins==5 and survival>=0
    comparisons[scenario]=dict(relative_change=ratio,paired_seed_differences=differences,mean_difference=delta,seed_sd=sd,ci95=[delta-ci,delta+ci],better_seeds=wins,survival_delta=survival,clear_advantage=qualifies)
    lines.append(f'| {scenario} | {ratio:+.2%} | {delta:+.6f} | {sd:.6f} | [{delta-ci:+.6f}, {delta+ci:+.6f}] | {wins} | {survival:+d} | {qualifies} |')
nominal=comparisons['nominal'];preserved=nominal['relative_change']<=.02 and nominal['survival_delta']>=0
regions=[k for k,v in comparisons.items() if v['clear_advantage']]
lines+=['',f'Nominal preservation criterion (≤2% RMSE increase, no survival decrease): **{preserved}**.',
        f'Clear advantage regions (≥5% mean reduction, all five seed differences negative, no survival decrease): **{", ".join(regions) if regions else "none"}**.','',
        'At 100 ms, the gate rejects every learned packet and must reproduce paired LQR exactly. This is a fallback contract, not an advantage over LQR.','',
        '## Interpretation and limits','',
        'The gate is a nominal linear model prediction using the same noisy state estimate, known speed, current map curvature and actuator encoder. It never receives true lateral velocity, hidden tire stiffness, friction or future noise. A predicted cost decrease is not a guarantee of realized tracking improvement. Candidate control is held for 50 ms in the predictor, followed by LQR continuation; future learned actions are not predicted.',
        '', 'This is a new surrogate development revision, not native Webots transfer validation of the new gate. Previous native Webots evidence applies to the previous controller. Paths and learned policy seeds are reused; only the noise streams are new. Service-time delays are simulated, not actual concurrent inference. No hard-real-time, stability, safety or publishability claim follows. No test-driven weight adjustment was made.']
(TEST/'report.md').write_text('\n'.join(lines)+'\n')
(TEST/'verification.json').write_text(json.dumps(dict(verified=True,episodes=len(rows),nominal_preserved=preserved,clear_advantage_regions=regions,comparisons=comparisons),indent=2)+'\n')
print('\n'.join(lines[-12:]))
