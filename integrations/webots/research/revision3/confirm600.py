"""Run two baseline continuations and the same paired development comparison."""
import argparse,concurrent.futures,csv,hashlib,importlib.util,itertools,json,subprocess,sys
from pathlib import Path
import torch
from stable_baselines3 import PPO
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
sys.path[:0]=[str(HERE),str(RESEARCH/'revision2'),str(RESEARCH)]
spec=importlib.util.spec_from_file_location('v3_eval',HERE/'evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--initial',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    protocol=json.loads((HERE/'confirmation.json').read_text());base=json.loads((HERE/'protocol.json').read_text());prior=json.loads((args.initial/'decision.json').read_text());gate=json.loads((ROOT/'results/revision2-development/freeze.json').read_text())
    for n,d in prior['source_sha256'].items():assert sha(RESEARCH/n)==d
    files=list(prior['source_sha256'])+['revision3/confirmation.json','revision3/confirm_train.py','revision3/confirm600.py']
    sources={n:sha(RESEARCH/n) for n in files};out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    for n in sources:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    (out/'start.json').write_text(json.dumps(dict(protocol=protocol,source_sha256=sources,initial_decision_sha256=sha(args.initial/'decision.json')),indent=2)+'\n')
    torch.set_num_threads(1);torch.set_num_interop_threads(1);ev.old.configure_lqr()
    def train(seed):
        name=f'baseline-{seed}'
        with (out/f'{name}.log').open('w') as log:subprocess.run([sys.executable,str(HERE/'confirm_train.py'),'--initial',str(args.initial/name),'--output',str(out/name)],stdout=log,stderr=subprocess.STDOUT,check=True)
        print(f'Continuation complete: {name}',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(train,protocol['seeds']))
    (out/'traces').mkdir();rows=[];policies={}
    with (out/'development.csv').open('w',newline='') as f:
        writer=None
        for seed in protocol['seeds']:
            folder=out/f'baseline-{seed}';meta=json.loads((folder/'complete.json').read_text());assert meta['steps']==600000 and sha(folder/'policy.zip')==meta['policy_sha256']
            model=PPO.load(folder/'policy.zip',device='cpu');assert model.num_timesteps==600000 and model.seed==seed
            policies[f'baseline-{seed}']=meta['policy_sha256']
            legacy_seed=protocol['legacy_reference_seed_map'][str(seed)];folder=ROOT/f'results/research-training/residual-{legacy_seed}'
            assert sha(folder/'policy.zip')==gate['policy_sha256'][f'residual-{legacy_seed}'];legacy=PPO.load(folder/'policy.zip',device='cpu')
            for speed,path,scenario,method in itertools.product(base['speeds'],base['paths'],base['scenarios'],protocol['methods']):
                policy=None if method=='lqr' else ev.InferencePolicy(legacy if method.startswith('legacy') else model,.5 if method=='legacy_gated' else .08)
                trace=out/'traces'/f'{method}-{scenario}.csv.gz' if seed==101 and speed==25 and path=='dlc220' else None
                row=ev.old.episode(policy,'lqr' if method=='lqr' else 'gated_residual',seed,speed,path,scenario,gate['selected_config'],protocol['development_noise_base'],trace);row['method']=method
                if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(f'Development seed{seed}: {len(rows)} episodes',flush=True)
    assert len(rows)==288 and sources=={n:sha(RESEARCH/n) for n in sources}
    (out/'complete.json').write_text(json.dumps(dict(episodes=288,source_sha256=sources,policy_sha256=policies,development_sha256=sha(out/'development.csv'),full_training_user_approved=False),indent=2)+'\n')
if __name__=='__main__':main()
