"""Full archived-DEV batch-one action parity for the portable NumPy worker."""
import argparse,importlib.util,json,sys
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/controller_review'))
from causal_student import load_causal,project_queries


def main():
    p=argparse.ArgumentParser();p.add_argument('--kit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.dont_write_bytecode=True;torch.set_num_threads(1)
    spec=importlib.util.spec_from_file_location('lans_portable_worker',a.kit/'laptop_benchmark.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.BASE=a.kit
    module.golden_check()
    x=project_queries(np.load(ROOT/'integrations/webots/results/revision8-student/data/dev.npz')['x']);results=[]
    for seed in (701,802,903):
        model=load_causal(ROOT/f'docs/research/causal-interface-2026-10-26/models/{seed}')
        with torch.no_grad():expected=model(torch.from_numpy(x)).numpy()
        exported=module.load(seed);actual=np.vstack([module.logits(exported,row[None,:]) for row in x])
        disagreements=int((expected.argmax(1)!=actual.argmax(1)).sum())
        assert disagreements==0
        results.append(dict(seed=seed,recorded_dev_rows=len(x),batch_one_action_disagreements=disagreements,
            max_logit_difference=float(np.max(np.abs(expected-actual)))))
    a.output.write_text(json.dumps(dict(export_batch_one_checks_pass=True,checks=results,
        windows_execution_verified=False,scope='Linux export arithmetic verification only; Windows laptop execution remains pending'),indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
