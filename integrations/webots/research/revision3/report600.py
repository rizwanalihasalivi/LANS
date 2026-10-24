"""Verify600k provenance, paired reproducibility and three-checkpoint development trend."""
import csv,hashlib,itertools,json,math,pickle,sys
from pathlib import Path
from statistics import mean
import torch
from stable_baselines3 import PPO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
OUT=ROOT/'results/revision3-600k';OLD=ROOT/'results/revision3-extended';FIRST=ROOT/'results/revision3-pilots'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(path):
    with path.open() as f:return list(csv.DictReader(f))
def key(r):return int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method']
def score(rs):return mean(float(r['penalized_rmse']) for r in rs)
def survivors(rs):return sum(r['survived']=='True' for r in rs)
def subset(rows,method,region=None,seed=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (seed is None or int(r['seed'])==seed)]

def main():
    torch.set_num_threads(1)
    protocol=json.loads((HERE/'confirmation.json').read_text());base=json.loads((HERE/'protocol.json').read_text())
    complete=json.loads((OUT/'complete.json').read_text());start=json.loads((OUT/'start.json').read_text())
    assert complete['source_sha256']==start['source_sha256'] and sha(OUT/'development.csv')==complete['development_sha256']
    for n,d in complete['source_sha256'].items():assert sha(RESEARCH/n)==d and sha(OUT/'source'/n)==d
    assert start['initial_decision_sha256']==sha(OLD/'decision.json')
    models=[]
    for seed in protocol['seeds']:
        name=f'baseline-{seed}';folder=OUT/name;prior=OLD/name;meta=json.loads((folder/'complete.json').read_text());resume=json.loads((folder/'resume.json').read_text())
        assert meta['initial_policy_sha256']==resume['initial_policy_sha256']==sha(prior/'policy.zip')
        assert meta['initial_normalization_sha256']==sha(prior/'normalization.pkl')
        assert meta['steps']==600000 and meta['additional_steps']==300000 and meta['candidate']=='baseline' and meta['residual_scale_rad']==.08
        assert sha(folder/'policy.zip')==meta['policy_sha256']==complete['policy_sha256'][name]
        for n,d in meta['source_sha256'].items():assert sha(folder/'source'/n)==d and sha(RESEARCH/n)==d
        model=PPO.load(folder/'policy.zip',device='cpu');assert model.num_timesteps==600000 and model.seed==seed
        optimizer=sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()})
        assert optimizer==meta['optimizer_steps_after']==[30000] and resume['optimizer_steps']==[15000]
        assert resume['effective_reset_seeds']==[seed+i for i in range(8)]
        with (folder/'normalization.pkl').open('rb') as f:norm=pickle.load(f)
        assert abs(norm.ret_rms.count-resume['normalization_count']-300000)<1e-6
        monitor_steps=0
        for path in folder.glob('*.monitor.csv'):
            with path.open() as f:
                next(f);monitor_steps+=sum(int(r['l']) for r in csv.DictReader(f))
        assert 0<=300000-monitor_steps<6400
        models.append(dict(seed=seed,total_steps=600000,additional_steps=300000,optimizer_step_counters=optimizer,normalization_count=float(norm.ret_rms.count),additional_completed_episode_steps=monitor_steps,initial_policy_sha256=meta['initial_policy_sha256'],policy_sha256=meta['policy_sha256']))
    rows=read(OUT/'development.csv');oldrows=read(OLD/'development.csv');firstrows=read(FIRST/'development.csv')
    assert sha(OLD/'development.csv')==json.loads((OLD/'decision.json').read_text())['development_csv_sha256']
    assert sha(FIRST/'development.csv')==json.loads((FIRST/'selection.json').read_text())['development_csv_sha256']
    expected=set(itertools.product(protocol['seeds'],base['speeds'],base['paths'],base['scenarios'],protocol['methods']))
    keys=[key(r) for r in rows];assert len(keys)==len(set(keys))==len(expected)==complete['episodes']==288 and set(keys)==expected
    lookup=dict(zip(keys,rows));old_lookup={key(r):r for r in oldrows}
    reproduced=0
    for k,r in lookup.items():
        assert int(r['steps'])<=int(r['scheduled_steps']) and float(r['max_rate'])<=.3500001 and math.isfinite(float(r['penalized_rmse']))
        if r['survived']=='True':assert r['steps']==r['scheduled_steps']
        if r['method']!='baseline600':
            previous=old_lookup[k]
            for field in ['penalized_rmse','rmse','survived','steps','scheduled_steps','noise_seed']:assert r[field]==previous[field],(k,field)
            reproduced+=1
        if r['scenario']=='latency100':
            lqr=lookup[k[:4]+('lqr',)];assert r['penalized_rmse']==lqr['penalized_rmse'] and float(r['active_fraction'])==0
    curve=[]
    for steps,data,method in [(100000,firstrows,'baseline'),(300000,oldrows,'baseline'),(600000,rows,'baseline600')]:
        for region in ['all',*base['scenarios']]:
            for seed in protocol['seeds']:
                chosen=subset(data,method,None if region=='all' else region,seed)
                curve.append(dict(steps=steps,region=region,seed=seed,episodes=len(chosen),survived=survivors(chosen),mean_penalized_rmse=score(chosen)))
    with (OUT/'learning-curve.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=curve[0]);w.writeheader();w.writerows(curve)
    new=subset(rows,'baseline600');old=subset(oldrows,'baseline');reference=subset(rows,'legacy_rescaled_gated')
    relative=(score(new)-score(old))/score(old);rescaled=(score(new)-score(reference))/score(reference)
    seed_differences=[score(subset(rows,'baseline600',seed=s))-score(subset(oldrows,'baseline',seed=s)) for s in protocol['seeds']]
    regional={r:(score(subset(rows,'baseline600',r))-score(subset(oldrows,'baseline',r)))/score(subset(oldrows,'baseline',r)) for r in protocol['active_regions']}
    rule=protocol['operational_progress_rule']
    checks=dict(improves_300k_by_1pct=relative<=-rule['minimum_relative_rmse_improvement_vs_300k'],beats_old_rescaled_by_1pct=rescaled<=-rule['minimum_relative_rmse_improvement_vs_old_rescaled'],both_seeds_improve=all(d<0 for d in seed_differences),regional_consistency=sum(d<0 for d in regional.values())>=rule['minimum_improving_active_regions'] and max(regional.values())<=rule['maximum_regional_degradation_vs_300k'],nominal_preservation=score(subset(rows,'baseline600','nominal'))<=1.02*score(subset(rows,'lqr','nominal')),survival=all(survivors(subset(rows,'baseline600',r))>=max(survivors(subset(oldrows,'baseline',r)),survivors(subset(rows,'lqr',r))) for r in base['scenarios']))
    decision=dict(verified=True,model_audits=models,episodes=288,reference_cells_reproduced_exactly=reproduced,baseline_survived=survivors(new),relative_rmse_change_vs_300k=relative,relative_rmse_change_vs_old_rescaled=rescaled,seed_mean_differences_vs_300k=seed_differences,active_region_changes_vs_300k=regional,checks=checks,material_progress=all(checks.values()),full_training_user_approved=False,final_reserved_evaluated=False)
    (OUT/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Baseline600k confirmation: development learning trend','',
           'Two existing300k baseline checkpoints continued for300k additional steps each. Both now contain600k total steps; no larger-network run, five-seed full training, final reserved evaluation or native transfer was performed.','',
           '| Checkpoint | Seed101 RMSE (m) | Seed202 RMSE (m) | Mean RMSE (m) | Survived /72 |','|---|---:|---:|---:|---:|']
    for steps,data,method in [(100000,firstrows,'baseline'),(300000,oldrows,'baseline'),(600000,rows,'baseline600')]:
        selected=subset(data,method);values=[score(subset(data,method,seed=s)) for s in protocol['seeds']]
        lines.append(f'| {steps//1000}k | {values[0]:.6f} | {values[1]:.6f} | {score(selected):.6f} | {survivors(selected)} |')
    lines+=['','| Region | 100k baseline | 300k baseline | 600k baseline | 600k change vs300k | LQR | Old-rescaled gated | Legacy gated |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for region in base['scenarios']:
        a=score(subset(firstrows,'baseline',region));b=score(subset(oldrows,'baseline',region));c=score(subset(rows,'baseline600',region))
        lines.append(f"| {region} | {a:.6f} | {b:.6f} | {c:.6f} | {(c-b)/b:+.2%} | {score(subset(rows,'lqr',region)):.6f} | {score(subset(rows,'legacy_rescaled_gated',region)):.6f} | {score(subset(rows,'legacy_gated',region)):.6f} |")
    lines+=['','## Frozen progress criteria','',f'Overall change600k vs300k: **{relative:+.3%}**. Versus old-rescaled: **{rescaled:+.3%}**. Negative favors600k.','', '| Check | Passed |','|---|---|']
    for name,value in checks.items():lines.append(f'| {name} | {value} |')
    lines+=['',f'Material improving trend under all predeclared operational checks: **{all(checks.values())}**. Full training remains unapproved.','',
            'These checks require ≥1% improvement against both300k and the old-rescaled anchor, better means for both seeds, improvement in at least4/5 active regions with no region >1% worse, preserved nominal accuracy and survival. They are budget-review thresholds, not statistical significance or a convergence proof. All per-region values and both seed means remain visible even if the rule fails.','',
            '## Provenance and limits','',f'Raw grid verified:288 episodes. All{reproduced} reference cells exactly reproduced the previous development errors/survival. Optimizer counters advance15000→30000 and normalization counts300k→600k; completed episode-step counts leave only valid unfinished tails. Initial and final model/source hashes are recorded.','',
            'Saved weights, Adam and reward normalization continue; simulator environments restart with SB3 model.seed+i, explicitly matching the prior effective behavior. This is not bit-for-bit uninterrupted600k training. The curve has three measured development checkpoints, not a dense convergence trajectory.',
            '', 'The same two training seeds, paths and development noise are repeatedly consulted at the user’s request. No reserved generalization claim follows. Legacy references have1M training steps and different model seeds0/1, while new policies use101/202. Their comparison does not isolate architecture/training benefit at matched budgets. Gate, ±.08 candidate range, reward and network remain unchanged. A plateau in these checks would not prove no future learning is possible, but it weakens the case for spending five million steps on this route.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for seed in protocol['seeds']:
        points=[r for r in curve if r['region']=='all' and r['seed']==seed]
        axes[0].plot([r['steps']/1000 for r in points],[r['mean_penalized_rmse'] for r in points],marker='o',label=f'seed {seed}')
    axes[0].set(xlabel='Total training steps (thousands)',ylabel='Development mean RMSE (m)',title='Measured checkpoint scores');axes[0].legend();axes[0].grid(alpha=.25)
    means=[mean(r['mean_penalized_rmse'] for r in curve if r['region']=='all' and r['steps']==s) for s in [100000,300000,600000]]
    axes[1].plot([100,300,600],means,marker='o',label='Baseline: two-seed mean')
    for method,label in [('legacy_rescaled_gated','Old rescaled'),('legacy_gated','Legacy gated'),('lqr','LQR')]:axes[1].axhline(score(subset(rows,method)),linestyle='--',label=label)
    axes[1].set(xlabel='Total training steps (thousands)',ylabel='Development mean RMSE (m)',title='Descriptive reference comparison');axes[1].legend(fontsize=8);axes[1].grid(alpha=.25)
    fig.savefig(OUT/'learning-curve.png',dpi=180);plt.close(fig)
    print(json.dumps(dict(relative_change_vs300k=relative,relative_change_vs_old_rescaled=rescaled,checks=checks,material_progress=all(checks.values()))))
if __name__=='__main__':main()
