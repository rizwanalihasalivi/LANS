"""All factorial arms reported; no best-arm choice on final evaluation."""
import argparse,csv,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
from bootstrap import HERE,RESEARCH
from evaluate10 import P,G,TEST_METHODS,DEV_METHODS,select,metrics


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
    audit(dev,DEV_METHODS,2052,'dev');audit(rows,TEST_METHODS,1188,'evaluation')
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
            assert c['anchor_coef']==(P['anchor']['coefficient'] if arm in P['anchor']['arms'] else 0.)
            assert c['mask_busy']==(arm in P['credit']['arms'])
            checkpoints.append(dict(steps=step,optimizer_steps=c['optimizer_steps']))
        training.append(dict(arm=arm,seed=meta['seed'],wall_s=meta['wall_s'],checkpoints=checkpoints,regions=meta['regions']))
    def subset(method,region=None,pair=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (pair is None or int(r['pair'])==pair)]
    score=lambda m,region=None,pair=None:metrics(subset(m,region,pair))['rmse']
    reduction=lambda m,b:1-score(m)/score(b)
    checks={}
    for arm in P['arms']:
        method=f'{arm}_selected'
        checks[arm]=dict(improves_student_by_1pct=reduction(method,'student')>=.01,
            improves_lqr_by_1pct=reduction(method,'lqr')>=.01,improves_fixed_by_1pct=reduction(method,'fixed_m004')>=.01,
            all_seed_means_better_than_student=all(score(method,pair=i)<score('student',pair=i) for i in range(3)),
            selections_eligible=all(selected[f'{arm}-{s}']['eligible'] for s in P['rl_seeds']),
            regional_survival=all(metrics(subset(method,r))['survived']>=max(metrics(subset(b,r))['survived'] for b in ('student','lqr','fixed_m004')) for r in G['scenarios']),
            nominal_preserved=score(method,'nominal')<=1.02*score('student','nominal'),
            other_active_regions_preserved=all(score(method,r)<=1.01*score('student',r) for r in G['scenarios'] if r not in ('nominal','latency100')))
    summary={m:dict(metrics(subset(m)),reduction_vs_lqr=reduction(m,'lqr'),reduction_vs_student=reduction(m,'student'),reduction_vs_fixed=reduction(m,'fixed_m004'),seed_sd=stdev(score(m,pair=i) for i in range(3))) for m in TEST_METHODS}
    contrasts=[]
    for i in range(3):
        plain,anchor,credit,combined=[score(f'{arm}_100k',pair=i) for arm in P['arms']]
        contrasts.append(dict(seed=P['rl_seeds'][i],anchor_without_credit_m=anchor-plain,credit_without_anchor_m=credit-plain,
            anchor_with_credit_m=combined-credit,credit_with_anchor_m=combined-anchor,interaction_m=combined-anchor-credit+plain))
    decision=dict(verified=True,protocol=P,training=training,selected=selected,summary=summary,checks=checks,
        passes_screen={arm:all(c.values()) for arm,c in checks.items()},endpoint_factorial_contrasts=contrasts,
        additional_rl_steps=1200000,dev_episodes=2052,evaluation_episodes=1188,gate_changed=False,promoted=False,native=False)
    (a.run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Student anchor and proposal-credit factorial pilot','',
        'Four arms, three matched fresh RL seeds each,100k transitions per job: **1.2million additional RL steps**. All exactly inherit the same paired supervised student and train-only standardizer. Critic/optimizer start fresh and matched. Gate, plant, observer, action grid and20 observed actor inputs remain frozen.',
        '', 'Anchor coefficient1 KL(student||actor) uses half current rollout observations and half existing Step2 TRAIN-observation replay; no new labels. Credit uses a training-only single-request200ms zero-innovation counterfactual through the actual worker/gate, and excludes ignored in-flight actions from actor/entropy gradients. It is model-predicted credit, not the actual future outcome.',
        '', 'Checkpoint choice uses2,052 development episodes and is frozen before1,188 fresh final episodes. Selected and100k endpoint results remain separate. Exact step0 retention is not a PPO gain.',
        '', '| Method | Survived /108 | Penalized RMSE (m) | Seed mean SD | Reduction vs student | Reduction vs LQR |','|---|---:|---:|---:|---:|---:|']
    for m,v in summary.items():lines.append(f'| {m} | {v["survived"]} | {v["rmse"]:.6f} | {v["seed_sd"]:.6f} | {v["reduction_vs_student"]:+.3%} | {v["reduction_vs_lqr"]:+.3%} |')
    lines+=['','## Development-only selection','','| Arm | RL seed | Selected steps | Eligible | DEV RMSE |','|---|---:|---:|---|---:|']
    for name,v in selected.items():lines.append(f'| {name.split("-")[0]} | {name.split("-")[1]} | {v["steps"]} | {v["eligible"]} | {v["rmse"]:.6f} |')
    lines+=['','## Frozen success screens','','| Check | '+' | '.join(P['arms'])+' |','|---|'+'---|'*4]
    for name in checks[P['arms'][0]]:lines.append('| '+name+' | '+' | '.join(str(checks[arm][name]) for arm in P['arms'])+' |')
    lines.append('| **All checks** | '+' | '.join(str(all(checks[arm].values())) for arm in P['arms'])+' |')
    lines+=['','## Regions: selected models','','| Region | Student | Plain | Anchor | Credit | Combined |','|---|---:|---:|---:|---:|---:|']
    for r in G['scenarios']:lines.append('| '+r+' | '+' | '.join(f'{score(m,r):.6f}' for m in ['student']+[f'{arm}_selected' for arm in P['arms']])+' |')
    lines+=['','## Seed means: selected models','','| RL seed | Student | Plain | Anchor | Credit | Combined |','|---|---:|---:|---:|---:|---:|']
    for i,s in enumerate(P['rl_seeds']):lines.append('| '+str(s)+' | '+' | '.join(f'{score(m,pair=i):.6f}' for m in ['student']+[f'{arm}_selected' for arm in P['arms']])+' |')
    lines+=['','## Fixed100k endpoint factorial contrasts','',
        'Negative RMSE differences favor the named factor. These are paired descriptive contrasts; three seed/noise pairs do not support a general significance or unique-cause claim. The credit factor includes both reward replacement and ignored-action masking. Selection is not used for factorial attribution.',
        '', '| RL seed | Anchor without credit (m) | Credit without anchor (m) | Interaction (m) |','|---|---:|---:|---:|']
    for v in contrasts:lines.append(f'| {v["seed"]} | {v["anchor_without_credit_m"]:+.6f} | {v["credit_without_anchor_m"]:+.6f} | {v["interaction_m"]:+.6f} |')
    lines+=['','## Compute and limits','','| Job | Wall seconds | Final Adam steps |','|---|---:|---:|']
    for v in training:lines.append(f'| {v["arm"]}-{v["seed"]} | {v["wall_s"]:.1f} | {v["checkpoints"][-1]["optimizer_steps"]:.0f} |')
    lines+=['','Same RL-transition budget is not equal wall compute: replay KL and reward forecasting add overhead. Counterfactual forecasts use current privileged state/parameters and zero future innovations; they can be biased and are never inference inputs. No actual future-noise stream is used in rewards. Physical execution and actor features remain identical.',
        '', 'Known geometries/condition families with fresh noise only. All failures retained with2.5m tails. Latency100ms is exact LQR fallback. No independently strong MPC comparison, native timing, unseen-domain validation, stability/safety proof or production promotion. No extra seeds, coefficients, rewards or teacher data were tried after outcomes.']
    (a.run/'report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(17,6),layout='constrained')
    axes[0].bar(TEST_METHODS,[summary[m]['rmse'] for m in TEST_METHODS]);axes[0].tick_params(axis='x',rotation=65)
    axes[0].set(ylabel='Mean penalized episode RMSE (m)',title='Fresh final test; all arms and endpoints')
    for arm in P['arms']:
        axes[1].plot(P['checkpoints'],[mean(float(r['penalized_rmse']) for r in dev if r['method']==f'{arm}_{step}') for step in P['checkpoints']],marker='o',label=arm)
    axes[1].axhline(mean(float(r['penalized_rmse']) for r in dev if r['method']=='student'),color='black',ls='--',label='student')
    axes[1].set(xlabel='RL transitions',ylabel='DEV penalized RMSE (m)',title='All predeclared checkpoints');axes[1].legend()
    fig.savefig(a.run/'comparison.png',dpi=180);plt.close(fig)
    print(json.dumps(dict(passes=decision['passes_screen'],summary=summary),indent=2))


if __name__=='__main__':main()
