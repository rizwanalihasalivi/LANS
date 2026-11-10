"""Read-only clustered comparisons of the frozen reliability confirmation."""
from pathlib import Path
import argparse,json
import numpy as np
from .calibrate import write,sha

SEEDS=(42,43,44)
ACTOR_MODES=('hybrid','v8_original','v8_common')


def assess(records,seed=41011000):
    ids=sorted({r['case']['id'] for r in records})
    lookup={(r['case']['id'],r['mode'],r['actor']):r for r in records}
    modes=sorted({r['mode'] for r in records});assert len(lookup)==len(records)==16*len(ids)
    fields=('rmse_m','heading_rms','rate_rms','progress_m')
    metrics={m:{f:float(np.mean([r[f] for r in records if r['mode']==m])) for f in fields} for m in modes}
    comparisons={}
    for mode in modes:
        if mode=='hybrid':continue
        clusters={};progress=[]
        for i in ids:
            refs=[lookup[i,mode,a] for a in SEEDS if mode in ACTOR_MODES] if mode in ACTOR_MODES else [lookup[i,mode,0]]
            hybrid=[lookup[i,'hybrid',a] for a in SEEDS];c=refs[0]['case']
            key=(c['scenario'],c['speed']>=12.,c['cluster_network'])
            clusters.setdefault(key,[]).append([np.mean([r['rmse_m'] for r in refs]),np.mean([r['rmse_m'] for r in hybrid])])
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in refs]) for r in hybrid)
        pairs=np.asarray([np.mean(v,axis=0) for _,v in sorted(clusters.items())]);means=pairs.mean(axis=0)
        draw=np.random.default_rng(seed).integers(len(pairs),size=(5000,len(pairs)));boot=pairs[draw].mean(axis=1)
        comparisons[mode]=dict(gain_percent=float(100*(1-means[1]/means[0])),
            ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist(),clusters=len(pairs),
            heading_ratio=metrics['hybrid']['heading_rms']/metrics[mode]['heading_rms'],
            rate_ratio=metrics['hybrid']['rate_rms']/metrics[mode]['rate_rms'],minimum_progress_ratio=float(min(progress)))
    reasons=[]
    for ref,target in [('lqr',5.),('optimized',1.)]:
        if comparisons[ref]['gain_percent']<target:reasons.append('mean_gain_'+ref)
        if comparisons[ref]['ci95_percent'][0]<=0:reasons.append('confidence_'+ref)
    for actor in SEEDS:
        rr=[lookup[i,'hybrid',actor] for i in ids];base=[lookup[i,'lqr',0] for i in ids]
        if np.mean([r['rmse_m'] for r in rr])>=np.mean([r['rmse_m'] for r in base]):reasons.append(f'actor_{actor}_no_gain')
        for field in ('heading_rms','rate_rms'):
            if np.mean([r[field] for r in rr])>1.1*np.mean([r[field] for r in base])+1e-12:reasons.append(f'actor_{actor}_{field}')
        if any(r['failed'] for r in rr):reasons.append(f'actor_{actor}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(rr,base)):reasons.append(f'actor_{actor}_progress')
    counts={mode:dict(episodes=sum(r['mode']==mode for r in records),
        failures=sum(r['failed'] for r in records if r['mode']==mode),
        collision_ticks=sum(r['collisions'] for r in records if r['mode']==mode),
        recourse_ticks=sum(r['recourse_ticks'] for r in records if r['mode']==mode),
        uncertified_recourse_ticks=sum(r['uncertified_recourse_ticks'] for r in records if r['mode']==mode)) for mode in modes}
    return dict(metrics=metrics,comparisons=comparisons,counts=counts,original_gate_passed=not reasons,reasons=reasons,
        no_quality_regression_to_lqr=all(comparisons['lqr'][f]<=1.+1e-12 for f in ('heading_ratio','rate_ratio')),
        no_quality_regression_to_original_v8=all(comparisons['v8_original'][f]<=1.+1e-12 for f in ('heading_ratio','rate_ratio')),
        requested_30_all_references=not reasons and all(c['gain_percent']>=30 for c in comparisons.values()),
        ci_lower_30_all_references=not reasons and all(c['ci95_percent'][0]>=30 for c in comparisons.values()),
        bootstrap_seed=seed,bootstrap_draws=5000,cluster_unit='scenario/speed-stratum/network-stratum; actors and replicate cases averaged within each cell')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);a=p.parse_args();root=a.root
    plan=json.loads((root/'plan.json').read_text());status=json.loads((root/'STATUS.json').read_text())
    assert status['complete'] and status['episodes']==2309
    all_records=[]
    for stage in plan['cases']:
        rr=json.loads((root/(stage+'-summary.json')).read_text());all_records.extend(rr)
        if stage in ('development','final','v8_reserved'):write(root/(stage+'-assessment.json'),assess(rr,plan['bootstrap_seed']))
    assert len(all_records)==2309 and all(r['plan_sha256']==sha(root/'plan.json') for r in all_records)
    current=[r for r in all_records if r['mode']=='hybrid']
    report=dict(episodes=len(all_records),current_hybrid_episodes=len(current),
        current_hybrid_failures=sum(r['failed'] for r in current),current_hybrid_collision_ticks=sum(r['collisions'] for r in current),
        current_hybrid_recourse_ticks=sum(r['recourse_ticks'] for r in current),
        current_hybrid_uncertified_recourse_ticks=sum(r['uncertified_recourse_ticks'] for r in current),
        current_python_safety_pass=all(not r['failed'] for r in current),policies_changed=False,
        original_v8_failures=sum(r['failed'] for r in all_records if r['mode']=='v8_original'),
        scope='Finite six-second scenarios; collision ticks sampled at 50 ms, no universal or native safety proof.')
    write(root/'safety-summary.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
