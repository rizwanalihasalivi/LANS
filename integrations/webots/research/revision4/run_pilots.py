"""Equal-budget pilots, predefined development screen, optional single-arm extension."""
import argparse,concurrent.futures,csv,hashlib,itertools,json,math,subprocess,sys
from pathlib import Path
from statistics import mean
import torch
from stable_baselines3 import PPO
from bootstrap import HERE,RESEARCH,ROOT
from comparison import configure_lqr
from mapping import RangeMappedPolicy
from evaluation import episode
PROTOCOL=json.loads((HERE/'protocol.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def score(rows,method,region=None,seed=None):
    subset=[r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (seed is None or r['seed']==seed)]
    return mean(r['penalized_rmse'] for r in subset)
def survive(rows,method,region):return sum(r['survived'] for r in rows if r['method']==method and r['scenario']==region)

def validate_screen_grid(rows, methods):
    """Reject missing/duplicate/unpaired development cells before spending decisions."""
    expected=set(itertools.product(PROTOCOL['pilot_seeds'],PROTOCOL['speeds'],PROTOCOL['paths'],PROTOCOL['scenarios']))
    grids={}
    for method in methods:
        grid={}
        for row in rows:
            if row['method']!=method:continue
            key=tuple(row[k] for k in ('seed','speed','path','scenario'))
            if key in grid:raise ValueError(f'duplicate {method} cell: {key}')
            if not math.isfinite(row['penalized_rmse']) or row['penalized_rmse']<0:
                raise ValueError('invalid RMSE score')
            grid[key]=row
        if set(grid)!=expected:raise ValueError(f'incomplete or unexpected {method} development grid')
        grids[method]=grid
    reference=grids['lqr']
    for method,grid in grids.items():
        for key,row in grid.items():
            if row['noise_seed']!=reference[key]['noise_seed']:
                raise ValueError(f'unpaired noise seed: {method} {key}')

def screening(rows,arm,threshold=.01,require_A=True):
    validate_screen_grid(rows,["lqr","A_hybrid",arm+"_hybrid"])
    method=arm+'_hybrid';active=['nominal','tire_mismatch','low_friction','sensor_stress','latency20'];stress=['tire_mismatch','low_friction','sensor_stress']
    changes={r:score(rows,method,r)/score(rows,'lqr',r)-1 for r in active}
    seed_stress=[mean(score(rows,method,r,s)-score(rows,'lqr',r,s) for r in stress) for s in PROTOCOL['pilot_seeds']]
    changes_A=[score(rows,method,seed=s)-score(rows,'A_hybrid',seed=s) for s in PROTOCOL['pilot_seeds']]
    severe=[r for r in rows if r['method']==method and r['scenario']=='latency100']
    lqr={(r['seed'],r['speed'],r['path'],r['scenario']):r for r in rows if r['method']=='lqr'}
    exact=all(r['active_fraction']==0 and r['penalized_rmse']==lqr[r['seed'],r['speed'],r['path'],r['scenario']]['penalized_rmse'] for r in severe)
    checks=dict(overall_vs_A=not require_A or score(rows,method)<=.99*score(rows,'A_hybrid'),both_seeds_vs_A=not require_A or all(d<0 for d in changes_A),two_stress_regions=sum(changes[r]<=-threshold for r in stress)>=2,both_seed_stress_means=all(d<0 for d in seed_stress),no_regional_regression=max(changes.values())<=.01,nominal_preservation=changes['nominal']<=.02,survival=all(survive(rows,method,r)>=max(survive(rows,'lqr',r),survive(rows,'A_hybrid',r) if require_A else 0) for r in PROTOCOL['scenarios']),severe_exact=exact)
    return dict(arm=arm,checks=checks,eligible=all(checks.values()),mean_rmse=score(rows,method),stress_mean=mean(score(rows,method,r) for r in stress),region_changes_vs_lqr=changes,seed_mean_differences_vs_A=changes_A,seed_stress_differences_vs_lqr=seed_stress)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);configure_lqr()
    frozen=json.loads((ROOT/'results/revision2-development/freeze.json').read_text())
    for n,d in frozen['source_sha256'].items():assert sha(RESEARCH/n)==d
    names=list(frozen['source_sha256'])+['revision3/mapping.py']+['revision4/'+n for n in ['bootstrap.py','protocol.json','reward_model.py','env4.py','train4.py','test_contracts.py','evaluation.py','run_pilots.py']]
    sources={n:sha(RESEARCH/n) for n in names}
    for n in sources:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    (out/'start.json').write_text(json.dumps(dict(protocol=PROTOCOL,source_sha256=sources,gate_freeze_sha256=sha(ROOT/'results/revision2-development/freeze.json')),indent=2)+'\n')
    def train(arm,seed,extension=False):
        name=f'{arm}-{seed}';target=out/('extension' if extension else 'training')/name;target.parent.mkdir(exist_ok=True)
        command=[sys.executable,str(HERE/'train4.py'),'--arm',arm,'--seed',str(seed),'--output',str(target)]
        if extension:command+=['--initial',str(out/'training'/name)]
        with (target.parent/f'{name}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        print(f'Trained {name}: {300000 if extension else 100000} steps',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda item:train(*item),itertools.product(PROTOCOL['arms'],PROTOCOL['pilot_seeds'])))
    def evaluate(arms,extension=False):
        destination=out/('extension-evaluation' if extension else 'evaluation');destination.mkdir();(destination/'traces').mkdir()
        rows=[];model_hashes={};methods=['lqr','standalone_full_reference','legacy_gated_reference',*[a+'_hybrid' for a in arms]]
        with (destination/'episodes.csv').open('w',newline='') as f:
            writer=None
            for seed in PROTOCOL['pilot_seeds']:
                models={}
                for arm in arms:
                    folder=out/('extension' if extension else 'training')/f'{arm}-{seed}';meta=json.loads((folder/'complete.json').read_text())
                    assert meta['steps']==(300000 if extension else 100000) and meta['arm']==arm and meta['seed']==seed and meta['policy_sha256']==sha(folder/'policy.zip')
                    for n,d in meta['source_sha256'].items():assert sha(RESEARCH/n)==d
                    models[arm+'_hybrid']=RangeMappedPolicy(PPO.load(folder/'policy.zip',device='cpu'));model_hashes[f'{arm}-{seed}']=meta['policy_sha256']
                refseed=PROTOCOL['reference_seed_map'][str(seed)]
                for role,label in [('full','standalone_full_reference'),('residual','legacy_gated_reference')]:
                    path=ROOT/f'results/research-training/{role}-{refseed}/policy.zip';assert sha(path)==frozen['policy_sha256'][f'{role}-{refseed}']
                    models[label]=PPO.load(path,device='cpu');model_hashes[f'{role}-reference-{seed}']=sha(path)
                for speed,path,scenario,method in itertools.product(PROTOCOL['speeds'],PROTOCOL['paths'],PROTOCOL['scenarios'],methods):
                    execution=method if method in ['lqr','standalone_full_reference'] else 'gated_residual'
                    trace=destination/'traces'/f'{method}-{scenario}.csv.gz' if seed==101 and speed==25 and path=='dlc220' else None
                    row=episode(None if method=='lqr' else models[method],execution,seed,speed,path,scenario,frozen['selected_config'],PROTOCOL['development_noise_base'],trace);row['method']=method
                    if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                    writer.writerow(row);f.flush();rows.append(row)
                print(f'Evaluated {"extension" if extension else "pilot"} seed{seed}: {len(rows)} episodes',flush=True)
        (destination/'complete.json').write_text(json.dumps(dict(episodes=len(rows),episodes_sha256=sha(destination/'episodes.csv'),model_sha256=model_hashes),indent=2)+'\n')
        return rows
    rows=evaluate(list(PROTOCOL['arms']));assert len(rows)==504
    candidates=[screening(rows,a) for a in ['B','C','D']];eligible=[a for a in candidates if a['eligible']]
    selected=min(eligible,key=lambda a:a['stress_mean'])['arm'] if eligible else None
    decision=dict(selected_for_extension=selected,assessments=candidates,source_sha256=sources,pilot_csv_sha256=sha(out/'evaluation/episodes.csv'),full_training_user_approved=False,reserved_evaluated=False)
    (out/'pilot-decision.json').write_text(json.dumps(decision,indent=2)+'\n');print(json.dumps(dict(extension_arm=selected,assessments=candidates)),flush=True)
    if selected:
        # Selection is written before any extension. No other arm receives extra budget.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda s:train(selected,s,True),PROTOCOL['pilot_seeds']))
        extended=evaluate([selected],True)
        # A100k remains a descriptive anchor; full review criteria depend on LQR, not A.
        assessment=screening(extended+[r for r in rows if r['method']=='A_hybrid'],selected,.05,False)
        (out/'extension-decision.json').write_text(json.dumps(dict(assessment=assessment,full_training_user_approved=False,reserved_evaluated=False),indent=2)+'\n')
    assert sources=={n:sha(RESEARCH/n) for n in sources}
    (out/'complete.json').write_text(json.dumps(dict(pilot_steps=800000,pilot_episodes=504,selected_for_extension=selected,extension_additional_steps=400000 if selected else 0,source_sha256=sources),indent=2)+'\n')
if __name__=='__main__':main()
