import boot8
import argparse
import hashlib
import json
import shutil
import sys
sys.path.insert(0,str(boot8.ROOT/'tools/reviewer_v5'))
from history5 import Bridge
from study8 import logits,np
import torch

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot8.Path,required=True);a=p.parse_args();out=a.run/'actors';out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    checks=[];rng=np.random.default_rng(832);x=rng.normal(0,.2,(2000,20)).astype(np.float32);x[:,[15,16,17,19]]=0
    for pair,seed in enumerate((701,802,903)):
        model=Bridge('student',pair);data=dict(mean=model.mean.numpy().copy(),std=model.std.numpy().copy())
        for i,layer in enumerate((model.net[0],model.net[2],model.net[4])):
            data[f'w{i}']=layer.weight.detach().numpy().T.copy();data[f'b{i}']=layer.bias.detach().numpy().copy()
        with torch.no_grad():expected=model(torch.from_numpy(x)).numpy()
        actual=logits(data,x);disagreements=int(np.count_nonzero(actual.argmax(1)!=expected.argmax(1)));assert disagreements==0
        assert np.max(np.abs(actual-expected))<1e-4 and np.count_nonzero(data['w0'][14])==0
        np.savez_compressed(out/f'student-{seed}.npz',**data)
        original=boot8.ROOT/f'docs/research/reviewer-history-v5/portable-actor/model-{seed}.npz'
        shutil.copy2(original,out/f'ppo-{seed}.npz')
        checks.append(dict(seed=seed,student_class_disagreements=disagreements,rows=len(x),ppo_origin_sha256=hashlib.sha256(original.read_bytes()).hexdigest()))
    sha={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
    (out/'manifest.json').write_text(json.dumps(dict(export_checks=checks,sha256=sha,new_training_steps=0),indent=2)+'\n')

if __name__=='__main__':main()
