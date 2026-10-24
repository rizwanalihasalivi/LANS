"""Compare close top-two pilots and block full training without clear regional evidence."""
import argparse,concurrent.futures,csv,hashlib,importlib.util,itertools,json,subprocess,sys
from pathlib import Path
from statistics import mean
import torch
from stable_baselines3 import PPO
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
sys.path[:0]=[str(HERE),str(RESEARCH/'revision2'),str(RESEARCH)]
spec=importlib.util.spec_from_file_location('v3_eval',HERE/'evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--initial',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    protocol=json.loads((HERE/'extension.json').read_text());base=json.loads((HERE/'protocol.json').read_text());stage1=json.loads((args.initial/'selection.json').read_text());gate=json.loads((ROOT/'results/revision2-development/freeze.json').read_text())
    for n,d in stage1['source_sha256'].items():assert sha(RESEARCH/n)==d
    ranked=sorted([r for r in stage1['rankings'] if r['eligible']],key=lambda r:r['mean_penalized_rmse'])
    assert [r['candidate'] for r in ranked[:2]]==protocol['top_two']
    gap=(ranked[1]['mean_penalized_rmse']-ranked[0]['mean_penalized_rmse'])/ranked[1]['mean_penalized_rmse'];assert gap<protocol['close_stage1_relative_gap']
    files=list(stage1['source_sha256'])+['revision3/extension.json','revision3/extend_train.py','revision3/extended_search.py']
    sources={n:sha(RESEARCH/n) for n in files};out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    for n in sources:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    (out/'start.json').write_text(json.dumps(dict(protocol=protocol,stage1_selection_sha256=sha(args.initial/'selection.json'),stage1_relative_gap=gap,source_sha256=sources),indent=2)+'\n')
    torch.set_num_threads(1);torch.set_num_interop_threads(1);ev.old.configure_lqr()
    def train(pair):
        candidate,seed=pair;name=f'{candidate}-{seed}'
        with (out/f'{name}.log').open('w') as log:subprocess.run([sys.executable,str(HERE/'extend_train.py'),'--initial',str(args.initial/name),'--output',str(out/name)],stdout=log,stderr=subprocess.STDOUT,check=True)
        print(f'Extended {name} to300k',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(train,itertools.product(protocol['top_two'],protocol['training_seeds'])))
    rows=[];policies={}
    with (out/'development.csv').open('w',newline='') as f:
        writer=None
        for seed in protocol['training_seeds']:
            models={}
            for candidate in protocol['top_two']:
                folder=out/f'{candidate}-{seed}';m=json.loads((folder/'complete.json').read_text());assert m['steps']==300000 and sha(folder/'policy.zip')==m['policy_sha256']
                models[candidate]=PPO.load(folder/'policy.zip',device='cpu');assert models[candidate].num_timesteps==300000
                policies[f'{candidate}-{seed}']=m['policy_sha256']
            legacy_seed=protocol['legacy_reference_seed_map'][str(seed)];folder=ROOT/f'results/research-training/residual-{legacy_seed}'
            assert sha(folder/'policy.zip')==gate['policy_sha256'][f'residual-{legacy_seed}'];legacy=PPO.load(folder/'policy.zip',device='cpu')
            for speed,path,scenario,method in itertools.product(base['speeds'],base['paths'],base['scenarios'],protocol['methods']):
                model=None if method=='lqr' else ev.InferencePolicy(legacy if method.startswith('legacy') else models[method],.5 if method=='legacy_gated' else .08)
                row=ev.old.episode(model,'lqr' if method=='lqr' else 'gated_residual',seed,speed,path,scenario,gate['selected_config'],protocol['development_noise_base'],None);row['method']=method
                if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(f'Extended development seed {seed}: {len(rows)} episodes',flush=True)
    assert len(rows)==360 and sources=={n:sha(RESEARCH/n) for n in sources}
    rule=protocol['clear_winner_rule'];assessments=[]
    def subset(method,region=None,seed=None):return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (seed is None or r['seed']==seed)]
    score=lambda rs:mean(r['penalized_rmse'] for r in rs)
    survived=lambda rs:sum(r['survived'] for r in rs)
    for candidate in protocol['top_two']:
        other=next(n for n in protocol['top_two'] if n!=candidate);a=subset(candidate);b=subset(other)
        relative=(score(a)-score(b))/score(b);seed_differences=[score(subset(candidate,seed=s))-score(subset(other,seed=s)) for s in protocol['training_seeds']]
        region_diffs={r:(score(subset(candidate,r))-score(subset(other,r)))/score(subset(other,r)) for r in protocol['active_regions']}
        survival_ok=all(survived(subset(candidate,r))>=max(survived(subset(other,r)),survived(subset('lqr',r))) for r in base['scenarios'])
        nominal=score(subset(candidate,'nominal'))/score(subset('lqr','nominal'))
        checks=dict(overall_margin=relative<=-rule['minimum_overall_relative_improvement_vs_other'],both_seed_means=sum(d<0 for d in seed_differences)>=2,regional_consistency=sum(d<0 for d in region_diffs.values())>=4 and max(region_diffs.values())<=rule['maximum_regional_rmse_degradation_vs_other'],nominal_preservation=nominal<=1.02,survival=survival_ok)
        assessments.append(dict(candidate=candidate,other=other,mean_penalized_rmse=score(a),survived=survived(a),relative_change_vs_other=relative,seed_mean_differences=seed_differences,region_relative_changes=region_diffs,nominal_ratio_vs_lqr=nominal,checks=checks,clear_winner=all(checks.values())))
    qualified=[r for r in assessments if r['clear_winner']];assert len(qualified)<=1
    selected=qualified[0]['candidate'] if qualified else None
    decision=dict(full_training_authorized=bool(qualified),selected_candidate=selected,selected_config=next(r['config'] for r in ranked if r['candidate']==selected) if selected else None,development_qualified=bool(qualified),assessments=assessments,source_sha256=sources,pilots_protocol_sha256=stage1['pilots_protocol_sha256'],extension_protocol_sha256=sha(HERE/'extension.json'),development_csv_sha256=sha(out/'development.csv'),policy_sha256=policies,development_episodes=360)
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    lines=['# Extended top-two pilot comparison','',f'Stage1 top-two relative gap: {gap:.3%}. Both configurations continued from100k to300k total steps at both pilot seeds. This adds800k steps; cumulative pilot training across both stages is1.6M.','', '| Region | Method | Survived /12 | Mean penalized RMSE (m) |','|---|---|---:|---:|']
    for region,method in itertools.product(base['scenarios'],protocol['methods']):
        rs=subset(method,region);lines.append(f'| {region} | {method} | {survived(rs)} | {score(rs):.6f} |')
    lines+=['','## Clear-winner checks','', '| Candidate | Overall RMSE | Change vs other | Seed mean differences (m) | Overall ≥1% | Both seeds | Region consistency | Nominal preserved | Survival | Clear winner |','|---|---:|---:|---|---|---|---|---|---|']
    for r in assessments:
        c=r['checks'];lines.append(f"| {r['candidate']} | {r['mean_penalized_rmse']:.6f} | {r['relative_change_vs_other']:+.2%} | {r['seed_mean_differences']} | {c['overall_margin']} | {c['both_seed_means']} | {c['regional_consistency']} | {c['nominal_preservation']} | {c['survival']} | {r['clear_winner']} |")
    lines+=['',f'Full training authorized by frozen criteria: **{bool(qualified)}**. Selected candidate: **{selected or "none"}**.','',
            'A clear winner requires ≥1% overall improvement over the other candidate, both seed means better, improvement in at least4/5 active regions with no region >1% worse, nominal within2% of LQR, and no regional survival loss. These are operational spending criteria, not a statistical-significance claim. No thresholds are relaxed after seeing results.','',
            'Old and old-rescaled policies are frozen1M-step reference models at seeds0/1; pilot models use seeds101/202 and300k total steps. Their noise is paired, but budgets/model seeds differ, so these anchors do not isolate retraining benefit. Final reserved tests remain untouched. Continuation retains policy/optimizer/normalization but restarts environments on a common fresh seed offset; it is not bit-for-bit uninterrupted300k training.']
    (out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(selected=selected,assessments=assessments)),flush=True)
if __name__=='__main__':main()
