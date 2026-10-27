"""Report every frozen arm and endpoint; never choose on final evaluation."""
import argparse,csv,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
from bootstrap import HERE,RESEARCH
from evaluate9 import P,G,TEST_METHODS,DEV_METHODS,select,metrics


def read(path):
    with path.open() as f:return list(csv.DictReader(f))


def audit(rows,methods,count,split):
    key=lambda r:(int(r['pair']),int(r['speed']),r['path'],r['scenario'],r['method'])
    keys=[key(r) for r in rows];expected=set(itertools.product(range(3),G['speeds'],G['paths'],G['scenarios'],methods))
    assert len(keys)==len(set(keys))==count and set(keys)==expected;lookup=dict(zip(keys,rows))
    for r in rows:
        n,N=int(r['steps']),int(r['scheduled_steps']);score=float(r['penalized_rmse']);rmse=float(r['rmse'])
        assert 0<n<=N and math.isfinite(score) and float(r['max_rate'])<=.3500001
        assert math.isclose(score,math.sqrt((n*rmse*rmse+(N-n)*6.25)/N),rel_tol=1e-10,abs_tol=1e-10)
        base=lookup[key(r)[:-1]+('lqr',)];assert r['noise_id']==base['noise_id']
        expected_id=P['splits'][split]+int(r['pair'])*10000+int(r['speed'])*100+list(G['paths']).index(r['path'])*10+list(G['scenarios']).index(r['scenario'])
        assert int(r['noise_id'])==expected_id
        if r['survived']=='True':assert n==N
        if r['scenario']=='latency100':assert r['penalized_rmse']==base['penalized_rmse'] and float(r['active_fraction'])==0


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    dev=read(a.run/'dev/episodes.csv');rows=read(a.run/'evaluation/episodes.csv')
    audit(dev,DEV_METHODS,1188,'dev');audit(rows,TEST_METHODS,756,'evaluation')
    assert not {r['noise_id'] for r in dev}&{r['noise_id'] for r in rows}
    selection=json.loads((a.run/'dev/selection.json').read_text());assert selection['protocol']==P and selection['selected']==select(dev)
    selected=selection['selected'];training=[]
    for pair,arm in itertools.product(range(3),P['arms']):
        folder=a.run/'training'/f'{arm}-{P["rl_seeds"][pair]}';meta=json.loads((folder/'complete.json').read_text())
        assert meta['protocol']==P and meta['steps']==100000
        checkpoints=[]
        for step in P['checkpoints']:
            c=json.loads((folder/f'checkpoint-{step}/complete.json').read_text());assert c['steps']==step and c['protocol']==P
            assert abs(c['reward_normalizer_count']-(step+.0001))<.001
            assert c['optimizer_steps']==0 if step==0 else 0<c['optimizer_steps']<=step/1000*50
            checkpoints.append(dict(steps=step,optimizer_steps=c['optimizer_steps']))
        training.append(dict(arm=arm,seed=meta['seed'],wall_s=meta['wall_s'],checkpoints=checkpoints,regions=meta['regions']))
    def subset(method,region=None,pair=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (pair is None or int(r['pair'])==pair)]
    score=lambda m,region=None,pair=None:metrics(subset(m,region,pair))['rmse']
    reduction=lambda m,b:1-score(m)/score(b)
    fine='finetune_selected'
    checks=dict(improves_student_by_1pct=reduction(fine,'student')>=.01,
        improves_lqr_by_1pct=reduction(fine,'lqr')>=.01,improves_fixed_by_1pct=reduction(fine,'fixed_m004')>=.01,
        all_seed_means_better_than_student=all(score(fine,pair=i)<score('student',pair=i) for i in range(3)),
        all_finetune_selections_eligible=all(selected[f'finetune-{s}']['eligible'] for s in P['rl_seeds']),
        regional_survival=all(metrics(subset(fine,r))['survived']>=max(metrics(subset(b,r))['survived'] for b in ('student','lqr','fixed_m004')) for r in G['scenarios']),
        nominal_preserved=score(fine,'nominal')<=1.02*score('student','nominal'),
        other_active_regions_preserved=all(score(fine,r)<=1.01*score('student',r) for r in G['scenarios'] if r not in ('nominal','latency100')))
    summary={m:dict(metrics(subset(m)),reduction_vs_lqr=reduction(m,'lqr'),reduction_vs_student=reduction(m,'student'),seed_sd=stdev(score(m,pair=i) for i in range(3))) for m in TEST_METHODS}
    decision=dict(verified=True,protocol=P,training=training,selected=selected,summary=summary,checks=checks,
        finetuning_passes_screen=all(checks.values()),additional_rl_steps=600000,dev_episodes=1188,evaluation_episodes=756,
        finetune_reduction_vs_scratch=reduction(fine,'scratch_selected'),gate_changed=False,promoted=False,native=False)
    (a.run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Step3: bounded PPO from the supervised student','',
        'Exact five-logit actor transfer; the original20 sensor/history inputs, fixed train-only standardizer, residual grid, execution gate, physical limits and reward are preserved. Critic and optimizer start fresh. Scratch shares standardization and additional RL budget; it does not share the privileged supervised pretraining budget.',
        '', 'Six jobs completed100k steps each (600k additional RL steps). Checkpoints0/25k/50k/100k were selected only on1188 development episodes, followed by756 fresh-noise evaluation episodes. Every endpoint is reported; no final-test selection.',
        '', '| Method | Survived /108 | Penalized RMSE (m) | Seed mean SD | Reduction vs LQR | Reduction vs student |','|---|---:|---:|---:|---:|---:|']
    for m,v in summary.items():lines.append(f'| {m} | {v["survived"]} | {v["rmse"]:.6f} | {v["seed_sd"]:.6f} | {v["reduction_vs_lqr"]:+.3%} | {v["reduction_vs_student"]:+.3%} |')
    lines+=['','## Development-only checkpoint choice','','| Arm | RL seed | Selected steps | Eligible | DEV RMSE |','|---|---:|---:|---|---:|']
    for name,v in selected.items():lines.append(f'| {name.split("-")[0]} | {name.split("-")[1]} | {v["steps"]} | {v["eligible"]} | {v["rmse"]:.6f} |')
    lines+=['','Step0 is the frozen student in the finetune arm. Selecting it means retaining the student, not demonstrating a PPO gain. All rejected candidates and reasons are in selection.json.',
        '', '## Regions: final evaluation','','| Region | '+' | '.join(TEST_METHODS)+' |','|---|'+'---:|'*len(TEST_METHODS)]
    for r in G['scenarios']:lines.append('| '+r+' | '+' | '.join(f'{score(m,r):.6f}' for m in TEST_METHODS)+' |')
    lines+=['','## Paired seed means','','| RL seed | Student | Scratch selected | Finetune selected | Finetune100k | Selected reduction vs student |','|---|---:|---:|---:|---:|---:|']
    for i,s in enumerate(P['rl_seeds']):lines.append(f'| {s} | {score("student",pair=i):.6f} | {score("scratch_selected",pair=i):.6f} | {score(fine,pair=i):.6f} | {score("finetune_100k",pair=i):.6f} | {1-score(fine,pair=i)/score("student",pair=i):+.3%} |')
    lines+=['','## Frozen success screen','','| Check | Pass |','|---|---|']+[f'| {k} | {v} |' for k,v in checks.items()]
    lines += ['',f'PPO improvement screen passed: **{all(checks.values())}**. Selected finetune reduction versus selected scratch: **{reduction(fine,"scratch_selected"):+.3%}**. This initialization comparison includes extra Step2 privileged-label pretraining; it is not an equal-total-compute comparison.',
        '', '## Interpretation limits','',
        'Known path geometries and six known condition families, three optimization/noise pairs. These results do not establish unseen-domain generalization, native timing, real-vehicle safety, or superiority to MPC. No new MPC experiment was run. RMSE averages penalized episode scores; unexecuted failed tails receive2.5m. Latency100ms is exact LQR fallback.',
        '', 'Training samples categorical actions; evaluation uses argmax. The five-class actor remains bounded by the existing gate. Target KL0.01 constrains each PPO update against its rollout policy, not against the original student; cumulative forgetting is possible. Standardization stays fixed and reward normalization continues across chunks. The existing reward was deliberately retained, so a tracking gain is measured rather than assumed from reward.',
        '', 'The protocol stops here regardless of outcome. No extra seeds, hyperparameter retries, teacher losses, gate change or production promotion is included.']
    (a.run/'report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    labels=['LQR','Fixed','Student','Scratch sel.','Fine sel.','Scratch100k','Fine100k']
    axes[0].bar(labels,[summary[m]['rmse'] for m in TEST_METHODS]);axes[0].tick_params(axis='x',rotation=35);axes[0].set(ylabel='Penalized episode RMSE (m)',title='Fresh paired evaluation; lower is better')
    for arm in P['arms']:
        values=[mean(float(r['penalized_rmse']) for r in dev if r['method']==f'{arm}_{step}') for step in P['checkpoints']]
        axes[1].plot(P['checkpoints'],values,marker='o',label=arm)
    axes[1].axhline(mean(float(r['penalized_rmse']) for r in dev if r['method']=='student'),ls='--',color='black',label='frozen student')
    axes[1].set(xlabel='Additional RL steps',ylabel='DEV penalized RMSE (m)',title='All predeclared checkpoints');axes[1].legend()
    fig.savefig(a.run/'comparison.png',dpi=180);plt.close(fig)
    print(json.dumps(dict(passes=all(checks.values()),summary=summary),indent=2))


if __name__=='__main__':main()
