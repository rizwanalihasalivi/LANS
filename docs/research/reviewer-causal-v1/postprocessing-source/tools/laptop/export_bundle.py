"""Export the actual trained causal models, with full archived-DEV action parity."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/controller_review'))
from causal_student import load_causal,project_queries


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-root',type=Path,default=ROOT/'docs/research/causal-interface-2026-10-26/models')
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    x=project_queries(np.load(ROOT/'integrations/webots/results/revision8-student/data/dev.npz')['x'])
    indices=np.linspace(0,len(x)-1,512,dtype=int);golden=dict(x=x[indices]);checks=[]
    for seed in (701,802,903):
        folder=a.model_root/str(seed)
        model=load_causal(folder);state=model.state_dict()
        data=dict(mean=state['mean'].numpy(),std=state['std'].numpy())
        for i,layer in enumerate((0,2,4)):
            data[f'w{i}']=state[f'net.{layer}.weight'].numpy().T.copy()
            data[f'b{i}']=state[f'net.{layer}.bias'].numpy().copy()
        np.savez_compressed(a.output/f'model-{seed}.npz',**data)
        with torch.no_grad():expected=model(torch.from_numpy(x)).numpy()
        actual=np.tanh(np.tanh(((x-data['mean'])/data['std'])@data['w0']+data['b0'])@data['w1']+data['b1'])@data['w2']+data['b2']
        different=int((actual.argmax(1)!=expected.argmax(1)).sum())
        if different:raise ValueError('export has action disagreements: '+str(different))
        golden[f'logits{seed}']=expected[indices]
        checks.append(dict(seed=seed,rows=len(x),action_disagreements=different,max_logit_error=float(np.max(np.abs(actual-expected))),
            source_model_sha256=hashlib.sha256((folder/'student.pt').read_bytes()).hexdigest()))
    np.savez_compressed(a.output/'golden.npz',**golden)
    for name in ('laptop_benchmark.py','precision_wait.py','RUN_WINDOWS.cmd','RUN_PYTHON310.cmd','README.md'):shutil.copy2(Path(__file__).parent/name,a.output/name)
    sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.output.iterdir() if p.is_file()}
    manifest=dict(profile='causal_query_v2',export_checks=checks,sha256=sha,
        model_provenance={str(seed):json.loads((a.model_root/str(seed)/'complete.json').read_text()) for seed in (701,802,903)})
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()
