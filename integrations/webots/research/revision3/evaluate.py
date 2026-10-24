"""Fresh paired comparison, reusing unchanged revision2 episodes and frozen gate."""
import argparse,csv,hashlib,importlib.util,itertools,json,sys,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
sys.path[:0]=[str(HERE),str(RESEARCH/'revision2'),str(RESEARCH)]
from mapping import legacy_units
spec=importlib.util.spec_from_file_location('unchanged_revision2_runner',RESEARCH/'revision2/run.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
PROTOCOL=json.loads((HERE/'protocol.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

class InferencePolicy:
    def __init__(self,model,scale):self.model=model;self.scale=scale;self.physical=[];self.saturated=[]
    def predict(self,*args,**kwargs):
        action,state=self.model.predict(*args,**kwargs)
        self.saturated.append(abs(float(action[0]))>=.999999)
        mapped=legacy_units(action) if self.scale==.08 else action
        self.physical.append(float(mapped[0])*.5)
        return mapped,state

def main():
    p=argparse.ArgumentParser();p.add_argument('--training',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wait-for-training',action='store_true');args=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);old.configure_lqr()
    freeze=json.loads((ROOT/'results/revision2-development/freeze.json').read_text())
    for n,d in freeze['source_sha256'].items():assert sha(RESEARCH/n)==d
    names=list(freeze['source_sha256'])+['revision3/evaluate.py','revision3/mapping.py','revision3/protocol.json','revision3/train.py','revision3/matched_env.py']
    hashes={name:sha(RESEARCH/name) for name in names}
    out=args.output;out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir()
    for name in hashes:
        target=out/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/name).read_bytes())
    (out/'start.json').write_text(json.dumps(dict(protocol=PROTOCOL,source_sha256=hashes,gate_freeze_sha256=sha(ROOT/'results/revision2-development/freeze.json')),indent=2)+'\n')
    rows=[];models={}
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=None
        for seed in PROTOCOL['seeds']:
            folder=args.training/f'residual-{seed}'
            if args.wait_for_training:
                deadline=time.monotonic()+3600
                if not (folder/'complete.json').exists():print(f'Waiting for matched residual seed {seed}',flush=True)
                while not (folder/'complete.json').exists():
                    if time.monotonic()>deadline:raise TimeoutError(str(folder))
                    time.sleep(5)
            meta=json.loads((folder/'complete.json').read_text())
            assert meta['steps']==1000000 and meta['seed']==seed and meta['residual_scale_rad']==.08 and meta['training_profile']=='range_matched_residual_v3'
            assert sha(folder/'policy.zip')==meta['policy_sha256']
            for name,digest in meta['source_sha256'].items():assert sha(RESEARCH/name)==digest and sha(folder/'source'/name)==digest
            legacy_folder=ROOT/f'results/research-training/residual-{seed}'
            assert sha(legacy_folder/'policy.zip')==freeze['policy_sha256'][f'residual-{seed}']
            new_model=PPO.load(folder/'policy.zip',device='cpu');legacy=PPO.load(legacy_folder/'policy.zip',device='cpu')
            assert new_model.num_timesteps==legacy.num_timesteps==1000000 and new_model.seed==legacy.seed==seed
            models[str(seed)]=dict(matched=meta['policy_sha256'],legacy=sha(legacy_folder/'policy.zip'))
            for speed,path,scenario,method in itertools.product(PROTOCOL['speeds'],PROTOCOL['paths'],PROTOCOL['scenarios'],PROTOCOL['methods']):
                base=legacy if method.startswith('legacy') else new_model
                policy=None if method=='lqr' else InferencePolicy(base,.5 if method=='legacy_gated' else .08)
                execution='lqr' if method=='lqr' else 'residual' if method=='matched_ungated' else 'gated_residual'
                trace=out/'traces'/f'{scenario}-{method}.csv.gz' if seed==0 and speed==25 and path=='dlc220' else None
                row=old.episode(policy,execution,seed,speed,path,scenario,freeze['selected_config'],PROTOCOL['test_noise_base'],trace);row['method']=method
                values=np.abs(policy.physical) if policy else np.array([])
                row.update(requested_residual_max_abs_rad=float(np.max(values)) if len(values) else 0.,requested_over_gate_cap_fraction=float(np.mean(values>.08000001)) if len(values) else 0.,normalized_saturation_fraction=float(np.mean(policy.saturated)) if policy else 0.,request_count=len(values))
                if method not in ('lqr','legacy_gated'):assert row['requested_residual_max_abs_rad']<=.08000001
                if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(f'Seed {seed} complete: {len(rows)} episodes',flush=True)
    assert len(rows)==PROTOCOL['episodes'] and hashes=={name:sha(RESEARCH/name) for name in hashes}
    (out/'complete.json').write_text(json.dumps(dict(episodes=len(rows),source_sha256=hashes,policy_sha256=models,episodes_sha256=sha(out/'episodes.csv')),indent=2)+'\n')
if __name__=='__main__':main()
