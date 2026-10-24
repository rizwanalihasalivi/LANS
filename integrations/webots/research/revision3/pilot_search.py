"""Equal-budget short training, paired development scoring, then immutable selection."""
import argparse,concurrent.futures,csv,hashlib,importlib.util,itertools,json,os,subprocess,sys
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
sys.path[:0]=[str(HERE),str(RESEARCH/'revision2'),str(RESEARCH)]
spec=importlib.util.spec_from_file_location('v3_eval',HERE/'evaluate.py');evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)
PROTOCOL=json.loads((HERE/'pilots.json').read_text());BASE=json.loads((HERE/'protocol.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);evaluation.old.configure_lqr()
    frozen=json.loads((ROOT/'results/revision2-development/freeze.json').read_text())
    for n,d in frozen['source_sha256'].items():assert sha(RESEARCH/n)==d
    names=list(frozen['source_sha256'])+['revision3/'+n for n in ['train.py','matched_env.py','mapping.py','protocol.json','pilots.json','pilot_env.py','pilot_search.py','evaluate.py','test_range.py']]
    sources={n:sha(RESEARCH/n) for n in names}
    for n in sources:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    (out/'start.json').write_text(json.dumps(dict(protocol=PROTOCOL,source_sha256=sources),indent=2)+'\n')
    def train(item):
        candidate,seed=item;folder=out/f'{candidate}-{seed}'
        with (out/f'{candidate}-{seed}.log').open('w') as log:
            subprocess.run([sys.executable,str(HERE/'train.py'),'--candidate',candidate,'--seed',str(seed),'--steps',str(PROTOCOL['pilot_steps']),'--output',str(folder)],stdout=log,stderr=subprocess.STDOUT,check=True)
        print(f'Pilot trained: {candidate}, seed {seed}',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(train,itertools.product(PROTOCOL['candidates'],PROTOCOL['pilot_seeds'])))
    rows=[];model_hashes={}
    with (out/'development.csv').open('w',newline='') as stream:
        writer=None
        for seed in PROTOCOL['pilot_seeds']:
            policies={}
            for candidate in PROTOCOL['candidates']:
                folder=out/f'{candidate}-{seed}';meta=json.loads((folder/'complete.json').read_text())
                assert meta['steps']==PROTOCOL['pilot_steps'] and meta['candidate']==candidate and meta['candidate_config']==PROTOCOL['candidates'][candidate]
                assert meta['policy_sha256']==sha(folder/'policy.zip')
                policies[candidate]=PPO.load(folder/'policy.zip',device='cpu');assert policies[candidate].num_timesteps==PROTOCOL['pilot_steps']
                model_hashes[f'{candidate}-{seed}']=meta['policy_sha256']
            for speed,path,scenario,candidate in itertools.product(BASE['speeds'],BASE['paths'],BASE['scenarios'],['lqr',*PROTOCOL['candidates']]):
                model=None if candidate=='lqr' else evaluation.InferencePolicy(policies[candidate],.08)
                row=evaluation.old.episode(model,'lqr' if candidate=='lqr' else 'gated_residual',seed,speed,path,scenario,frozen['selected_config'],PROTOCOL['development_noise_base'],None);row['method']=candidate
                if writer is None:writer=csv.DictWriter(stream,fieldnames=row);writer.writeheader()
                writer.writerow(row);stream.flush();rows.append(row)
            print(f'Development seed {seed}: {len(rows)} episodes',flush=True)
    assert len(rows)==360 and sources=={n:sha(RESEARCH/n) for n in sources}
    baseline=[r for r in rows if r['method']=='lqr'];bnom=np.mean([r['penalized_rmse'] for r in baseline if r['scenario']=='nominal']);bsurv=sum(r['survived'] for r in baseline)
    rankings=[]
    for candidate,config in PROTOCOL['candidates'].items():
        subset=[r for r in rows if r['method']==candidate];surv=sum(r['survived'] for r in subset)
        nominal=np.mean([r['penalized_rmse'] for r in subset if r['scenario']=='nominal'])
        rankings.append(dict(candidate=candidate,config=config,survived=surv,episodes=len(subset),nominal_ratio=float(nominal/bnom),eligible=bool(surv>=bsurv and nominal<=1.02*bnom),mean_penalized_rmse=float(np.mean([r['penalized_rmse'] for r in subset]))))
    eligible=[r for r in rankings if r['eligible']]
    winner=min(eligible,key=lambda r:r['mean_penalized_rmse']) if eligible else min(rankings,key=lambda r:(-r['survived'],r['mean_penalized_rmse']))
    selected=dict(selected_candidate=winner['candidate'],selected_config=winner['config'],development_qualified=winner['eligible'],rankings=rankings,development_episodes=360,pilot_training_steps=800000,development_csv_sha256=sha(out/'development.csv'),pilots_protocol_sha256=sha(HERE/'pilots.json'),source_sha256=sources,policy_sha256=model_hashes)
    (out/'selection.json').write_text(json.dumps(selected,indent=2)+'\n')
    lines=['# Pilot selection','', 'Four candidates, two training seeds each, 100k steps per run. All scores are paired development results, not final tests.','', '| Candidate | Survived / 72 | Mean penalized RMSE (m) | Nominal / LQR | Eligible |','|---|---:|---:|---:|---|']
    for r in rankings:lines.append(f"| {r['candidate']} | {r['survived']} | {r['mean_penalized_rmse']:.6f} | {r['nominal_ratio']:.6f} | {r['eligible']} |")
    lines+=['',f"Selected **{winner['candidate']}** by the predeclared rule. Freeze this selection before full training and reserved evaluation. A short pilot ranking does not guarantee the same ranking after one million steps."]
    (out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(winner=winner,rankings=rankings)),flush=True)
if __name__=='__main__':main()
