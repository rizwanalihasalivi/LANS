"""Verify actual episode/selector records and report finite-policy headroom."""
import argparse,csv,gzip,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
import numpy as np
from bootstrap import HERE,RESEARCH
P=json.loads((HERE/'protocol.json').read_text());G=json.loads((RESEARCH/'revision6/protocol.json').read_text())


def read(path):
    with path.open() as f:return list(csv.DictReader(f))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    rows=read(a.run/'episodes.csv');complete=json.loads((a.run/'complete.json').read_text())
    expected=set(itertools.product(G['seeds'],G['speeds'],G['paths'],G['scenarios'],P['methods']))
    key=lambda r:(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method'])
    keys=[key(r) for r in rows];assert len(keys)==len(set(keys))==len(expected)==complete['episodes']==864 and set(keys)==expected
    lookup=dict(zip(keys,rows));prior={key(r):r for r in read(RESEARCH.parent/'results/revision6-correction/evaluation/episodes.csv')}
    parity=0;selector_checks=0;trace_rows=0;max_baseline_difference=0.
    for r in rows:
        n,N=int(r['steps']),int(r['scheduled_steps']);rmse=float(r['rmse']);score=float(r['penalized_rmse'])
        assert 0<n<=N and math.isfinite(score) and float(r['max_rate'])<=.3500001
        assert math.isclose(score,math.sqrt((n*rmse**2+(N-n)*6.25)/N),rel_tol=1e-10,abs_tol=1e-10)
        if r['survived']=='True':assert n==N
        baseline=lookup[key(r)[:-1]+('lqr',)]
        assert r['noise_seed']==baseline['noise_seed']
        if r['scenario']=='latency100':
            assert float(r['correction_rms_rad'])==0. and r['penalized_rmse']==baseline['penalized_rmse']
        if r['method']=='fixed_zero':assert r['penalized_rmse']==baseline['penalized_rmse']
        mapping={'lqr':'lqr','fixed_m008':'constant_negative','fixed_p008':'constant_positive'}
        if r['method'] in mapping:
            old=prior[key(r)[:-1]+(mapping[r['method']],)]
            difference=abs(score-float(old['penalized_rmse']));max_baseline_difference=max(max_baseline_difference,difference)
            assert difference<1e-10 and r['survived']==old['survived'] and r['steps']==old['steps'];parity+=1
        if r['method'].startswith('oracle'):
            counts=json.loads(r['selection_counts']);assert sum(counts)==int(r['selector_calls'])
            assert int(r['branch_rollouts'])==int(r['selector_calls'])*5
            file=a.run/f'seed-{r["seed"]}'/'traces'/f'{r["speed"]}-{r["path"]}-{r["scenario"]}-{r["method"]}.csv.gz'
            with gzip.open(file,'rt') as f:
                data=list(csv.DictReader(f))
            assert len(data)==n;trace_rows+=len(data)
            for tick in data:
                selected=int(float(tick['selected_index']))
                if selected<0:continue
                costs=[float(tick[k]) for k in ['cost_m008','cost_m004','cost_zero','cost_p004','cost_p008']]
                assert all(math.isfinite(c) for c in costs) and costs[selected]==min(costs)
                assert float(tick['proposal'])==P['residual_candidates_rad'][selected]
                selector_checks+=1
    def subset(method,region=None,seed=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (seed is None or int(r['seed'])==seed)]
    score=lambda rs:mean(float(r['penalized_rmse']) for r in rs)
    survival=lambda rs:sum(r['survived']=='True' for r in rs)
    fixed=[m for m in P['methods'] if m.startswith('fixed')]
    best=min(fixed,key=lambda m:score(subset(m)))
    relative=lambda method,reference:1-score(subset(method))/score(subset(reference))
    checks=dict(gain_vs_lqr_at_least_1pct=relative('oracle_gated','lqr')>=.01,
        gain_vs_best_global_fixed_at_least_1pct=relative('oracle_gated',best)>=.01,
        all_noise_seed_means_better_than_lqr=all(score(subset('oracle_gated',seed=s))<score(subset('lqr',seed=s)) for s in G['seeds']),
        regional_survival_preserved=all(survival(subset('oracle_gated',r))>=max(survival(subset('lqr',r)),survival(subset(best,r))) for r in G['scenarios']),
        no_active_region_over_1pct_worse=all(score(subset('oracle_gated',r))<=1.01*score(subset('lqr',r)) for r in G['scenarios'] if r!='latency100'))
    decision=dict(verified=True,episodes=len(rows),reference_cells_parity=parity,max_reference_rmse_difference=max_baseline_difference,
        oracle_trace_rows_checked=trace_rows,selector_choices_checked=selector_checks,best_global_fixed=best,
        gated_reduction_vs_lqr=relative('oracle_gated','lqr'),gated_reduction_vs_best_fixed=relative('oracle_gated',best),
        bypass_reduction_vs_lqr=relative('oracle_bypass','lqr'),checks=checks,promising_finite_diagnostic=all(checks.values()),
        absolute_ceiling=False,learnability_proven=False,gate_deployment_changed=False,step2_started=False,training=False,reserved=False,native=False)
    (a.run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Step1: finite-grid privileged oracle headroom','',
        'Five proposed residuals: −0.08/−0.04/0/+0.04/+0.08rad.200ms hold-candidate lookahead, recomputed on every available submission; actual gate, delayed packets, observer and actuator evolve in each cloned branch. Only one real10ms transition is applied after selection.',
        '', '**This is not an absolute/theoretical performance ceiling.** It is one finite-action, finite-horizon receding policy, with true model/state and future sensor-noise privilege. It can be worse than a fixed policy over a whole episode; its minimum window cost does not establish global minimum RMSE or student learnability.',
        '', '| Method | Survived /108 | Mean penalized episode RMSE (m) | Noise-seed mean SD | Reduction vs LQR |',
        '|---|---:|---:|---:|---:|']
    for method in P['methods']:
        means=[score(subset(method,seed=s)) for s in G['seeds']]
        lines.append(f'| {method} | {survival(subset(method))} | {score(subset(method)):.6f} | {stdev(means):.6f} | {relative(method,"lqr"):+.3%} |')
    lines+=['',f'Best global fixed proposal on these development data: **{best}**. This is a descriptive baseline selection, not an untouched-test win. All five fixed candidates remain reported.',
        '', '| Region | LQR | Best fixed | Gated oracle | Bypass oracle | Gated reduction vs LQR |','|---|---:|---:|---:|---:|---:|']
    for region in G['scenarios']:
        base=score(subset('lqr',region));v=score(subset('oracle_gated',region))
        lines.append(f'| {region} | {base:.6f} | {score(subset(best,region)):.6f} | {v:.6f} | {score(subset("oracle_bypass",region)):.6f} | {1-v/base:+.3%} |')
    lines+=['', '| Noise seed | LQR | Gated oracle | Bypass oracle | Gated reduction vs LQR |','|---|---:|---:|---:|---:|']
    for seed in G['seeds']:
        base=score(subset('lqr',seed=seed));v=score(subset('oracle_gated',seed=seed))
        lines.append(f'| {seed} | {base:.6f} | {v:.6f} | {score(subset("oracle_bypass",seed=seed)):.6f} | {1-v/base:+.3%} |')
    lines+=['','## Frozen diagnostic spending screen','','| Check | Passed |','|---|---|']
    lines += [f'| {k} | {v} |' for k,v in checks.items()]
    lines += ['',f'Promising finite diagnostic: **{all(checks.values())}**. Neither a pass nor a fail proves a theoretical ceiling, a tight gate, student learnability or safety. No Step2/training or gate deployment change is launched.',
        '', '## Verification and limits','',
        f'{parity} stored reference cells (LQR and both±.08 constants) match revision6 within1e-10m; maximum difference {max_baseline_difference:.3g}m. Checked {selector_checks:,} selected minima in {trace_rows:,} oracle trajectory rows. All five branch costs and selected proposals are retained. Zero proposal equals LQR; every100ms stale case exactly falls back.',
        '', 'Three noise repetitions, three speeds, two known paths, six regions,864 paired episodes. Noise IDs intentionally reuse development cells to verify parity. No new learned model, reserved data, native simulator or physical vehicle evidence. Primary metric is full-episode error with2.5m failed-tail fill; lookahead uses cumulative lateral error only. Window cost can trade heading/control behavior against short-term lateral error, so it is not a globally optimal controller.',
        '', 'Bypass is an evaluation-only combined removal of performance/envelope/persistence/weight restrictions, with unchanged proposal/physical limits and stale fallback. It cannot isolate one threshold, and its authority is not enabled in production. Gate-based branches still use only estimated state/measured speed; hidden physical parameters and future noise are used by the privileged selector, not the gate.',
        '', 'PPO receives tracking/survival rewards on every tick. Sparse accepted corrections mean sparse action-dependent feedback, not an absence of all reward. A later teacher/student protocol must remove or explicitly study future-noise privilege; this diagnostic is not ready-to-use supervision.']
    (a.run/'report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    axes[0].bar(P['methods'],[score(subset(m)) for m in P['methods']]);axes[0].tick_params(axis='x',rotation=55)
    axes[0].set(ylabel='Mean penalized episode RMSE (m)',title='Finite-policy diagnostic, not a theoretical ceiling')
    for method in (best,'oracle_gated','oracle_bypass'):
        axes[1].plot(list(G['scenarios']),[100*(1-score(subset(method,r))/score(subset('lqr',r))) for r in G['scenarios']],marker='o',label=method)
    axes[1].axhline(0,color='black',lw=.8);axes[1].tick_params(axis='x',rotation=50)
    axes[1].set(ylabel='RMSE reduction vs LQR (%)',title='Positive is better; privileged diagnostic only');axes[1].legend()
    fig.savefig(a.run/'headroom.png',dpi=180);plt.close(fig)
    print(json.dumps({k:decision[k] for k in ('verified','episodes','gated_reduction_vs_lqr','gated_reduction_vs_best_fixed','bypass_reduction_vs_lqr','promising_finite_diagnostic')}))


if __name__=='__main__':main()
