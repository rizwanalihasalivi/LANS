"""Verify the frozen pilot and report every arm/region without post-result tuning."""
import argparse,csv,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
import numpy as np
from bootstrap import HERE
P=json.loads((HERE/'protocol.json').read_text())


def read(path):
    with path.open() as f:return list(csv.DictReader(f))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    evaluation=a.run/'evaluation';rows=read(evaluation/'episodes.csv')
    assert json.loads((evaluation/'complete.json').read_text())['episodes']==648
    key=lambda r:(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method'])
    expected=set(itertools.product(P['seeds'],P['speeds'],P['paths'],P['scenarios'],P['methods']))
    keys=[key(r) for r in rows];assert len(keys)==len(set(keys))==648 and set(keys)==expected
    lookup=dict(zip(keys,rows))
    for r in rows:
        n,N=int(r['steps']),int(r['scheduled_steps']);raw=float(r['rmse']);score=float(r['penalized_rmse'])
        assert 0<n<=N and math.isfinite(score) and float(r['max_rate'])<=.3500001
        assert math.isclose(score,math.sqrt((n*raw*raw+(N-n)*6.25)/N),abs_tol=1e-10,rel_tol=1e-10)
        if r['survived']=='True':assert n==N
        baseline=lookup[key(r)[:-1]+('lqr',)]
        assert r['noise_seed']==baseline['noise_seed'] and r['scheduled_steps']==baseline['scheduled_steps']
        if r['scenario']=='latency100' and r['method'] not in ('lqr','mpc'):
            assert r['penalized_rmse']==baseline['penalized_rmse'] and float(r['correction_rms_rad'])==0.
    model_audits=[]
    for arm,seed in itertools.product(P['arms'],P['seeds']):
        folder=a.run/'training'/f'{arm}-{seed}';meta=json.loads((folder/'complete.json').read_text())
        assert meta['steps']==100000 and meta['seed']==seed and meta['arm']==arm and meta['protocol']==P
        assert meta['observation_dimensions']==20 and meta['residual_scale_rad']==.08
        # Check critical source snapshots against the frozen current implementations.
        for name in ('revision6/environment.py','revision6/train.py','revision6/protocol.json','revision5/execution.py',
                     'revision5/execution_env.py','revision4/reward_model.py','revision2/gating.py','revision2/plant.py','core.py','comparison.py','comparison-protocol.json'):
            assert (folder/'source'/name).read_bytes()==(HERE.parent/name).read_bytes(),name
        monitor_steps=0
        for path in folder.glob('*.monitor.csv'):
            with path.open() as f:next(f);monitor_steps+=sum(int(r['l']) for r in csv.DictReader(f))
        assert 0<=100000-monitor_steps<6400
        diagnostics=read(folder/'diagnostics.csv');assert len(diagnostics)==100 and int(diagnostics[-1]['steps'])==100000
        model_audits.append(dict(arm=arm,seed=seed,steps=meta['steps'],completed_monitor_steps=monitor_steps,
            wall_s=meta['wall_s'],active_training_fraction=float(diagnostics[-1]['active_fraction']),
            relative_training_reward=float(diagnostics[-1]['reward_relative'])))
    def subset(method,region=None,seed=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (seed is None or int(r['seed'])==seed)]
    score=lambda rs:mean(float(r['penalized_rmse']) for r in rs)
    survived=lambda rs:sum(r['survived']=='True' for r in rs)
    changes=lambda x,y:score(subset(x))/score(subset(y))-1
    regions=list(P['scenarios']);active=[r for r in regions if r!='latency100']
    progress=dict(improves_direct_by_1pct=changes('execution','direct')<=-.01,
        at_least_two_seed_improvements=sum(score(subset('execution',seed=s))<score(subset('direct',seed=s)) for s in P['seeds'])>=2,
        regional_survival=all(survived(subset('execution',r))>=max(survived(subset('direct',r)),survived(subset('lqr',r))) for r in regions),
        nominal_preserved=score(subset('execution','nominal'))<=1.02*score(subset('lqr','nominal')),
        no_active_region_over_1pct_worse=all(score(subset('execution',r))<=1.01*score(subset('lqr',r)) for r in active),
        severe_exact=all(float(r['correction_rms_rad'])==0. for r in subset('execution','latency100')))
    learning=dict(beats_lqr_by_1pct=changes('execution','lqr')<=-.01,
        beats_positive_by_1pct=changes('execution','constant_positive')<=-.01,
        beats_negative_by_1pct=changes('execution','constant_negative')<=-.01)
    mpc_advantage=dict(improves_mpc_by_1pct=changes('execution','mpc')<=-.01,
        all_seed_improvements=all(score(subset('execution',seed=s))<score(subset('mpc',seed=s)) for s in P['seeds']),
        regional_survival=all(survived(subset('execution',r))>=survived(subset('mpc',r)) for r in regions))
    solver_calls=sum(int(r['mpc_calls']) for r in rows);solver_fallbacks=sum(int(r['mpc_fallbacks']) for r in rows)
    decision=dict(verified=True,episodes=len(rows),training_steps=600000,training_models=model_audits,
        progress_checks=progress,primary_progress=all(progress.values()),learning_checks=learning,
        learning_benefit=all(progress.values()) and all(learning.values()),mpc_advantage_checks=mpc_advantage,
        mpc_advantage=all(mpc_advantage.values()),mpc_calls=solver_calls,mpc_fallbacks=solver_fallbacks,
        full_training_launched=False,final_reserved=False,native=False)
    (a.run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Correction-quality pilot: fixed100k endpoints','',
        'Six policies from scratch, two arms × three seeds ×100k = **600,000 training steps**. Training protocol freeze `1201f8d`; evaluator/MPC freeze `55b8ff8`. No best-checkpoint selection, extensions or post-result tuning.',
        '', 'Both policies deploy through the same frozen gate. Direct means direct-residual **training**, not ungated deployment. Same20 observations, PPO settings, nominal training distribution and executed-command reward; service0 in both training arms. Only training execution changes.',
        '', '## Paired development comparison','',
        '| Method | Survived /108 | Mean episode RMSE (m) | Seed-mean SD (m) | Change vs LQR |',
        '|---|---:|---:|---:|---:|']
    for method in P['methods']:
        rs=subset(method);seedmeans=[score(subset(method,seed=s)) for s in P['seeds']]
        lines.append(f'| {method} | {survived(rs)} | {score(rs):.6f} | {stdev(seedmeans):.6f} | {changes(method,"lqr"):+.3%} |')
    lines += ['', 'Negative change means lower error. Equal weighting across episode/seed means; failure tails filled at2.5m. Different clocks and reused baseline calculations are not independent training replicas.', '',
        '| Region | LQR | MPC | Constant + | Constant − | Direct-trained | Execution-trained |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for region in regions:
        lines.append('| '+region+' | '+' | '.join(f'{score(subset(m,region)):.6f}' for m in P['methods'])+' |')
    lines += ['', '## Paired training-effect uncertainty','',
        '| Seed | Direct-trained | Execution-trained | Difference (m) |','|---|---:|---:|---:|']
    diffs=[]
    for seed in P['seeds']:
        x=score(subset('execution',seed=seed));y=score(subset('direct',seed=seed));diffs.append(x-y)
        lines.append(f'| {seed} | {y:.6f} | {x:.6f} | {x-y:+.6f} |')
    margin=4.3026527299*stdev(diffs)/math.sqrt(3)
    lines += ['',f'Descriptive t(2)95% interval for mean execution−direct difference: [{mean(diffs)-margin:+.6f}, {mean(diffs)+margin:+.6f}]m. Three seeds, no multiplicity correction or general-significance claim.',
        '', '## Frozen operational criteria','']
    for name,checks in [('Primary training effect',progress),('Learning-specific benefit',learning),('MPC comparison',mpc_advantage)]:
        lines += [f'### {name}','','| Check | Passed |','|---|---|']
        lines += [f'| {k} | {v} |' for k,v in checks.items()];lines += ['']
    lines += [f'Primary progress: **{decision["primary_progress"]}**. Learning benefit including primary checks: **{decision["learning_benefit"]}**. Declared MPC advantage: **{decision["mpc_advantage"]}**.',
        '', '## Training diagnostics','', '| Arm | Seed | Wall seconds | Gate active | Mean relative reward |', '|---|---:|---:|---:|---:|']
    for m in model_audits:lines.append(f'| {m["arm"]} | {m["seed"]} | {m["wall_s"]:.2f} | {m["active_training_fraction"]:.2%} | {m["relative_training_reward"]:+.6f} |')
    lines += ['', '## MPC and scope limits','',
        f'MPC calls: **{solver_calls}**, solver/constraint fallbacks: **{solver_fallbacks}**. Fallback uses the same local LQR and remains counted. This is a declared nominal linear/actuator constrained MPC, not an exhaustive optimal nonlinear MPC comparison.',
        '', 'Same noisy sensor/estimator, observed-speed channel, three curvature previews, nonlinear plant and physical constraints across learned/MPC methods. Local LQR uses its original current-curvature design. MPC re-plans locally; service0/20/100ms delays apply to learned/constant proposals, not an artificial delay imposed on local baselines. Wall solver/inference values are diagnostics under concurrent CPU load, not real-time guarantees.',
        '', 'Known sine120/DLC220 geometries and fresh development noise at three speeds/six regions. No final reserved noise, native Webots campaign, real-vehicle safety, stability or unseen-path claim. Training stays nominal and synchronous; tests under delayed/mismatched deployment do not claim those conditions were trained. The 600k budget is a pilot, not convergence proof.',
        '', '**Stop at the predeclared pilot endpoint.** No automatic full training, new reward, gate change, arm selection or extra budget is authorized by this report.']
    (a.run/'report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    methods=P['methods'];values=[score(subset(m)) for m in methods]
    axes[0].bar(methods,values,yerr=[stdev([score(subset(m,seed=s)) for s in P['seeds']]) for m in methods],capsize=3)
    axes[0].tick_params(axis='x',rotation=45);axes[0].set(ylabel='Mean penalized episode RMSE (m)',title='All108 paired cells per method; error bars: seed SD')
    for method in ('direct','execution','mpc'):
        axes[1].plot(regions,[100*(score(subset(method,r))/score(subset('lqr',r))-1) for r in regions],marker='o',label=method)
    axes[1].axhline(0,color='black',lw=.8);axes[1].tick_params(axis='x',rotation=45)
    axes[1].set(ylabel='RMSE change vs LQR (%)',title='Negative is better; development grid only');axes[1].legend()
    fig.savefig(a.run/'comparison.png',dpi=180);plt.close(fig)
    print(json.dumps({k:decision[k] for k in ['verified','episodes','primary_progress','learning_benefit','mpc_advantage','mpc_fallbacks']}))


if __name__=='__main__':main()
