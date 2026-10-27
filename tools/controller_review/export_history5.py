"""Versioned NumPy actor export, including nonzero causal-history parity tests."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/reviewer_v5'))
import boot5
import numpy as np
import torch
from stable_baselines3 import PPO
from causal_student import project_queries
from history5 import PROFILE


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--arm',choices=['history','nohistory'],required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    x=project_queries(np.load(ROOT/'integrations/webots/results/revision8-student/data/dev.npz')['x'])
    x[:,14]=np.sin(np.arange(len(x),dtype=np.float64)*.173).astype(np.float32)
    indices=np.linspace(0,len(x)-1,512,dtype=int);golden=dict(x=x[indices]);checks=[];origins={}
    for pair,seed in enumerate((701,802,903)):
        source=args.run/f'{args.arm}-{pair}/policy.zip';model=PPO.load(source,device='cpu')
        meta=json.loads((source.parent/'complete.json').read_text());assert meta['steps']==100000 and meta['profile']==PROFILE
        f=model.policy.features_extractor;data=dict(mean=f.mean.numpy().copy(),std=f.std.numpy().copy())
        for i,layer in enumerate((model.policy.mlp_extractor.policy_net[0],model.policy.mlp_extractor.policy_net[2],model.policy.action_net)):
            data[f'w{i}']=layer.weight.detach().numpy().T.copy();data[f'b{i}']=layer.bias.detach().numpy().copy()
        assert data['mean'][14]==0 and data['std'][14]==1
        if args.arm=='nohistory':assert np.count_nonzero(data['w0'][14])==0
        with torch.no_grad():
            tx=torch.from_numpy(x);expected=model.policy.action_net(model.policy.mlp_extractor.forward_actor(model.policy.extract_features(tx))).numpy()
        actual=np.tanh(np.tanh(((x-data['mean'])/data['std'])@data['w0']+data['b0'])@data['w1']+data['b1'])@data['w2']+data['b2']
        disagreement=int(np.count_nonzero(actual.argmax(1)!=expected.argmax(1)));assert disagreement==0,'Export class parity failed'
        error=float(np.max(np.abs(actual-expected)));assert error<1e-4
        np.savez_compressed(out/f'model-{seed}.npz',**data);golden[f'logits{seed}']=expected[indices]
        checks.append(dict(seed=seed,rows=len(x),action_disagreements=disagreement,max_logit_error=error,nonzero_causal_history_tested=True))
        origins[str(seed)]=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),arm=args.arm,additional_steps=meta['steps'],
            source_v3_steps=100000,history_column_norm=meta['history_column_norm'],research_diagnostic_only=True)
    np.savez_compressed(out/'golden.npz',**golden)
    sha={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
    (out/'manifest.json').write_text(json.dumps(dict(profile=PROFILE,history_semantics='14=known prior filtered residual/0.08;15/16/17/19zero',
        sha256=sha,export_checks=checks,model_provenance=origins),indent=2)+'\n');print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
