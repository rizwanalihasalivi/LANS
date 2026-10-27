import boot9
import argparse
import hashlib
import json
import numpy as np
import torch
from stable_baselines3 import PPO
from model9 import Bridge
from features9 import PROFILE,NEW

def logits(data,x):return np.tanh(np.tanh(((x-data['mean'])/data['std'])@data['w0']+data['b0'])@data['w1']+data['b1'])@data['w2']+data['b2']

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot9.Path,required=True);a=p.parse_args();out=a.run/'actors';out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    rng=np.random.default_rng(932);x=rng.normal(0,.2,(2000,20)).astype(np.float32);x[:,[16,17]]=0;x[:,15]=rng.uniform(0,1,len(x));x[:,19]=rng.uniform(0,1,len(x));checks=[]
    golden={arm:dict(x=x[:512]) for arm in ('legacy_history','causal_history')}
    for pair,seed in enumerate((701,802,903)):
        for kind in ('student','old','legacy_history','causal_history'):
            if kind in golden:
                source=a.run/f'{kind}-{pair}/policy.zip';model=PPO.load(source,device='cpu');f=model.policy.features_extractor;layers=(model.policy.mlp_extractor.policy_net[0],model.policy.mlp_extractor.policy_net[2],model.policy.action_net)
                with torch.no_grad():expected=model.policy.action_net(model.policy.mlp_extractor.forward_actor(model.policy.extract_features(torch.from_numpy(x)))).numpy()
            else:
                model=Bridge('student' if kind=='student' else 'ppo',pair);f=model;layers=(model.net[0],model.net[2],model.net[4]);source=None
                with torch.no_grad():expected=model(torch.from_numpy(x)).numpy()
            data=dict(mean=f.mean.numpy().copy(),std=f.std.numpy().copy())
            for i,layer in enumerate(layers):data[f'w{i}']=layer.weight.detach().numpy().T.copy();data[f'b{i}']=layer.bias.detach().numpy().copy()
            actual=logits(data,x);bad=int(np.count_nonzero(actual.argmax(1)!=expected.argmax(1)));assert bad==0 and np.max(np.abs(actual-expected))<1e-4
            if kind!='causal_history':assert np.count_nonzero(data['w0'][list(NEW)])==0
            np.savez_compressed(out/f'{kind}-{seed}.npz',**data);checks.append(dict(kind=kind,seed=seed,rows=len(x),class_disagreements=bad))
            if kind in golden:
                folder=a.run/'runtime-actors'/kind;folder.mkdir(parents=True,exist_ok=True);np.savez_compressed(folder/f'model-{seed}.npz',**data);golden[kind][f'logits{seed}']=expected[:512]
    for arm,values in golden.items():
        folder=a.run/'runtime-actors'/arm;np.savez_compressed(folder/'golden.npz',**values)
        sha={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.iterdir() if f.is_file()}
        (folder/'manifest.json').write_text(json.dumps(dict(profile=PROFILE,arm=arm,new_features='14filtermemory;15past responseEWMA;19past qualificationage;16/17zero',sha256=sha,
            source_policy_sha256={str(seed):hashlib.sha256((a.run/f'{arm}-{pair}/policy.zip').read_bytes()).hexdigest() for pair,seed in enumerate((701,802,903))},diagnostic_only=True),indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(export_checks=checks,sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}),indent=2)+'\n')

if __name__=='__main__':main()
