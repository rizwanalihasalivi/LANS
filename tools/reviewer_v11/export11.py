import boot11
import argparse
import hashlib
import json
import shutil
import numpy as np
import torch
from stable_baselines3 import PPO
from features9 import PROFILE

def logits(m,x):return np.tanh(np.tanh(((x-m['mean'])/m['std'])@m['w0']+m['b0'])@m['w1']+m['b1'])@m['w2']+m['b2']
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot11.Path,required=True);a=p.parse_args();out=a.run/'actors';out.mkdir(exist_ok=False);runtime=a.run/'runtime-actors';runtime.mkdir(exist_ok=False);torch.set_num_threads(1)
    rng=np.random.default_rng(11032);x=rng.normal(0,.2,(2000,20)).astype(np.float32);x[:,[16,17]]=0;x[:,[15,19]]=rng.uniform(0,1,(len(x),2));golden=dict(x=x[:512]);checks=[]
    for pair,seed in enumerate((701,802,903)):
        for target,source in (('student_rk','student'),('oldppo_rk','causal_history')):shutil.copy2(boot11.ROOT/f'docs/research/reviewer-pipeline-v9/actors/{source}-{seed}.npz',out/f'{target}-{seed}.npz')
        model=PPO.load(a.run/f'training-{pair}/policy.zip',device='cpu');f=model.policy.features_extractor;layers=(model.policy.mlp_extractor.policy_net[0],model.policy.mlp_extractor.policy_net[2],model.policy.action_net)
        data=dict(mean=f.mean.numpy().copy(),std=f.std.numpy().copy())
        for i,layer in enumerate(layers):data[f'w{i}']=layer.weight.detach().numpy().T.copy();data[f'b{i}']=layer.bias.detach().numpy().copy()
        with torch.no_grad():expected=np.concatenate([model.policy.action_net(model.policy.mlp_extractor.forward_actor(model.policy.extract_features(torch.from_numpy(xx[None,:])))).numpy() for xx in x])
        actual=np.concatenate([logits(data,xx[None,:]) for xx in x]);errors=int(np.count_nonzero(actual.argmax(1)!=expected.argmax(1)));assert errors==0 and np.max(np.abs(actual-expected))<1e-4
        np.savez_compressed(out/f'newppo_rk-{seed}.npz',**data);np.savez_compressed(runtime/f'model-{seed}.npz',**data);golden[f'logits{seed}']=expected[:512]
        checks.append(dict(pair=pair,rows=len(x),single_row_class_disagreements=errors,max_abs_logit_error=float(np.max(np.abs(actual-expected)))))
    np.savez_compressed(runtime/'golden.npz',**golden)
    (runtime/'manifest.json').write_text(json.dumps(dict(profile=PROFILE,diagnostic_only=True,controller='audited_history_comp_v10',sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in runtime.iterdir() if f.is_file()}),indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(checks=checks,sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
