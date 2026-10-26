"""Separate teacher quality, supervised fit and closed-loop student performance."""
import argparse,csv,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
import numpy as np
from bootstrap import HERE,RESEARCH
P=json.loads((HERE/'protocol.json').read_text());G=json.loads((RESEARCH/'revision6/protocol.json').read_text())
METHODS=['lqr','fixed_m004','teacher','student','previous_ppo']


def read(path):
    with path.open() as f:return list(csv.DictReader(f))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    data=a.run/'data';counts=json.loads((data/'complete.json').read_text())['counts'];ids={};split_audits={}
    for split,expected in [('train',216),('dev',108)]:
        episodes=json.loads((data/f'{split}-episodes.json').read_text());assert len(episodes)==expected
        ids[split]={row['noise_id'] for row in episodes}
        with np.load(data/f'{split}.npz') as z:
            assert z['x'].shape==(counts[split]['rows'],20) and z['costs'].shape==(len(z['x']),5)
            assert np.isfinite(z['x']).all() and np.isfinite(z['costs']).all()
            assert np.array_equal(np.bincount(z['labels'],minlength=5),counts[split]['classes'])
            for row in episodes:
                selected=z['groups']==row['group'];assert int(selected.sum())==row['rows']
                assert np.all(z['ticks'][selected]%5==0)
            chosen=z['labels'];costs=z['costs'];best=costs.min(1);selected=costs[np.arange(len(costs)),chosen]
            abstained=costs[:,2]-best<=np.maximum(1e-7,.001*costs[:,2])
            assert np.all(chosen[abstained]==2)
            assert np.all(selected[~abstained]==best[~abstained])
            split_audits[split]=dict(episodes=len(episodes),rows=len(z['x']),class_counts=counts[split]['classes'],
                nonzero_label_fraction=float(np.mean(chosen!=2)),noise_ids=len(ids[split]))
    assert not ids['train']&ids['dev']
    audits=[]
    with np.load(data/'train.npz') as train:
        expected_mean=train['x'].mean(0,dtype=np.float64).astype(np.float32)
        expected_std=np.maximum(train['x'].std(0,dtype=np.float64),.001).astype(np.float32)
    for seed in P['student']['seeds']:
        folder=a.run/'students'/str(seed);meta=json.loads((folder/'complete.json').read_text());epochs=read(folder/'epochs.csv')
        assert meta['protocol']==P and meta['seed']==seed and len(epochs)==meta['epochs_executed']==20
        best=min(epochs,key=lambda r:(float(r['dev_regret']),int(r['epoch'])))
        assert meta['selected_epoch']==int(best['epoch']) and meta['best_dev_regret']==float(best['dev_regret'])
        with np.load(folder/'normalization.npz') as norm:
            np.testing.assert_array_equal(norm['mean'],expected_mean);np.testing.assert_array_equal(norm['std'],expected_std)
        audits.append(dict(seed=seed,selected_epoch=meta['selected_epoch'],dev_regret=meta['best_dev_regret'],
            dev_accuracy=float(best['accuracy']),nonzero_accuracy=float(best['nonzero_label_accuracy']) if best['nonzero_label_accuracy'] else None,wall_s=meta['wall_s']))
    rows=read(a.run/'evaluation/episodes.csv');assert json.loads((a.run/'evaluation/complete.json').read_text())['episodes']==540
    key=lambda r:(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method'])
    keys=[key(r) for r in rows];expected=set(itertools.product(P['student']['seeds'],G['speeds'],G['paths'],G['scenarios'],METHODS))
    assert len(keys)==len(set(keys))==len(expected)==540 and set(keys)==expected
    lookup=dict(zip(keys,rows));ids['evaluation']={int(r['noise_id']) for r in rows}
    assert not ids['evaluation']&(ids['train']|ids['dev'])
    for r in rows:
        n,N=int(r['steps']),int(r['scheduled_steps']);rmse=float(r['rmse']);score=float(r['penalized_rmse'])
        assert 0<n<=N and math.isfinite(score) and float(r['max_rate'])<=.3500001
        assert math.isclose(score,math.sqrt((n*rmse*rmse+(N-n)*6.25)/N),rel_tol=1e-10,abs_tol=1e-10)
        baseline=lookup[key(r)[:-1]+('lqr',)]
        assert r['noise_id']==baseline['noise_id']
        if r['survived']=='True':assert n==N
        if r['scenario']=='latency100':assert r['penalized_rmse']==baseline['penalized_rmse'] and float(r['active_fraction'])==0.
    def subset(method,region=None,seed=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (seed is None or int(r['seed'])==seed)]
    score=lambda rs:mean(float(r['penalized_rmse']) for r in rs)
    survivors=lambda rs:sum(r['survived']=='True' for r in rs)
    reduction=lambda m,b:1-score(subset(m))/score(subset(b))
    checks=dict(improves_lqr_by_1pct=reduction('student','lqr')>=.01,improves_fixed_by_1pct=reduction('student','fixed_m004')>=.01,
        all_seed_means_better_than_lqr=all(score(subset('student',seed=s))<score(subset('lqr',seed=s)) for s in P['student']['seeds']),
        regional_survival=all(survivors(subset('student',r))>=max(survivors(subset('lqr',r)),survivors(subset('fixed_m004',r))) for r in G['scenarios']),
        nominal_preserved=score(subset('student','nominal'))<=1.02*score(subset('lqr','nominal')),
        no_active_region_over_1pct_worse=all(score(subset('student',r))<=1.01*score(subset('lqr',r)) for r in G['scenarios'] if r!='latency100'))
    decision=dict(verified=True,dataset=split_audits,students=audits,evaluation_episodes=540,
        student_reduction_vs_lqr=reduction('student','lqr'),student_reduction_vs_fixed=reduction('student','fixed_m004'),
        student_reduction_vs_previous_ppo=reduction('student','previous_ppo'),teacher_reduction_vs_lqr=reduction('teacher','lqr'),
        checks=checks,student_passes_screen=all(checks.values()),actual_future_noise_used_in_teacher=False,
        student_privileged_inputs=False,ppo_finetuning=False,gate_changed=False,promoted=False,native=False)
    (a.run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Step2: expected-cost teacher and supervised student','',
        'Teacher uses current privileged state/plant but **no actual future measurement noise**. Future costs average zero and independent antithetic Gaussian forecasts. Student sees only the20 original observed/history features. Five residual classes and frozen gate/physical limits remain unchanged.',
        '', '## Data and supervised selection','', '| Split | Episodes | Label rows | Nonzero label fraction | Class counts −.08/−.04/0/+.04/+.08 |','|---|---:|---:|---:|---|']
    for split,v in split_audits.items():lines.append(f'| {split} | {v["episodes"]} | {v["rows"]} | {v["nonzero_label_fraction"]:.2%} | {v["class_counts"]} |')
    lines+=['','Episode/noise IDs are disjoint across train/dev/evaluation. Data come from zero/fixed/random-grid behavior; no final evaluation data or teacher rollout was appended to training. Standardization is train-only. Model selection uses DEV label regret, not closed-loop evaluation scores.',
        '', '| Optimization seed | Selected epoch /20 | DEV mean normalized regret | DEV label accuracy | Nonzero-label accuracy |','|---|---:|---:|---:|---:|']
    for v in audits:
        useful='unavailable' if v['nonzero_accuracy'] is None else f'{v["nonzero_accuracy"]:.2%}'
        lines.append(f'| {v["seed"]} | {v["selected_epoch"]} | {v["dev_regret"]:.6f} | {v["dev_accuracy"]:.2%} | {useful} |')
    lines+=['','Accuracy is a supervised diagnostic, not tracking performance. Zero abstention and class imbalance make overall accuracy insufficient.',
        '', '## Fresh paired closed-loop evaluation','', '| Method | Survived /108 | Mean penalized RMSE (m) | Seed-mean SD | Reduction vs LQR |','|---|---:|---:|---:|---:|']
    for m in METHODS:
        seedmeans=[score(subset(m,seed=s)) for s in P['student']['seeds']]
        lines.append(f'| {m} | {survivors(subset(m))} | {score(subset(m)):.6f} | {stdev(seedmeans):.6f} | {reduction(m,"lqr"):+.3%} |')
    lines+=['','| Region | LQR | Fixed −.04 | Teacher | Student | Previous PPO |','|---|---:|---:|---:|---:|---:|']
    for region in G['scenarios']:lines.append('| '+region+' | '+' | '.join(f'{score(subset(m,region)):.6f}' for m in METHODS)+' |')
    lines+=['','## Frozen student screen','','| Check | Passed |','|---|---|']
    lines += [f'| {k} | {v} |' for k,v in checks.items()]
    lines+=['',f'Qualified by the declared screen: **{all(checks.values())}**. Student reduction vs previous PPO: **{reduction("student","previous_ppo"):+.3%}**; different training data/budget and privileged labels make that a descriptive reference, not an equal-budget causal conclusion.',
        '', '## Limits and stop','',
        'Three supervised optimization/noise pairs and known paths/condition families; no broad generalization or native claim. Teacher uses hidden current state/plant and a finite three-sample200ms counterfactual, so its performance is neither a deployable result nor an absolute ceiling. Future forecasts are independent of actual future draws, but the student still faces current hidden-state/parameter ambiguity.',
        '', 'Mean episode RMSE is failure-penalized at2.5m for unexecuted tails. Every method/scenario/failure remains included. At100ms all methods use stale fallback and match LQR. No teacher/student result is transferred from Step1 without evaluation here.',
        '', 'No further dataset, epochs, search, PPO fine-tuning, production gate change or automatic promotion follows this report. Step3 is not launched.']
    (a.run/'report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    axes[0].bar(METHODS,[score(subset(m)) for m in METHODS]);axes[0].tick_params(axis='x',rotation=35)
    axes[0].set(ylabel='Mean penalized episode RMSE (m)',title='Fresh paired closed-loop comparison')
    for m in ['teacher','student','fixed_m004']:
        axes[1].plot(list(G['scenarios']),[100*(1-score(subset(m,r))/score(subset('lqr',r))) for r in G['scenarios']],marker='o',label=m)
    axes[1].axhline(0,color='black',lw=.8);axes[1].tick_params(axis='x',rotation=45);axes[1].legend()
    axes[1].set(ylabel='RMSE reduction vs LQR (%)',title='Positive is better; teacher privilege disclosed')
    fig.savefig(a.run/'comparison.png',dpi=180);plt.close(fig)
    print(json.dumps({k:decision[k] for k in ['verified','evaluation_episodes','student_reduction_vs_lqr','student_reduction_vs_fixed','student_reduction_vs_previous_ppo','teacher_reduction_vs_lqr','student_passes_screen']}))


if __name__=='__main__':main()
