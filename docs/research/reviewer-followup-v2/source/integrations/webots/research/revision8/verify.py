"""Check selected model tensors against DEV-only selection and frozen data code."""
import argparse,json
from pathlib import Path
import numpy as np
import torch
from bootstrap import HERE,RESEARCH
from student import load,validation,P


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args();torch.set_num_threads(1)
    for name in ('revision8/student.py','revision8/teacher.py','revision8/data.py','revision8/protocol.json','revision7/kernels.py',
                 'core.py','protocol.json','comparison.py','comparison-protocol.json','revision2/plant.py','revision2/gating.py','revision5/execution.py'):
        assert (a.run/'source'/name).read_bytes()==(RESEARCH/name).read_bytes(),name
    dev=np.load(a.run/'data/dev.npz');dc=dev['costs'];regret=np.clip((dc-dc.min(1,keepdims=True))/np.maximum(dc[:,2:3],1e-4),0,1)
    models=[]
    for seed in P['student']['seeds']:
        folder=a.run/'students'/str(seed);meta=json.loads((folder/'complete.json').read_text());model=load(folder)
        assert meta['seed']==seed and meta['profile']=='supervised_grid_v8' and meta['epochs_executed']==20
        metrics=validation(model,torch.from_numpy(dev['x']),dev['labels'],regret,dev['groups'])
        assert abs(metrics['dev_regret']-meta['best_dev_regret'])<1e-12
        norm=np.load(folder/'normalization.npz')
        np.testing.assert_array_equal(model.mean.detach().numpy(),norm['mean']);np.testing.assert_array_equal(model.std.detach().numpy(),norm['std'])
        a1,_=model.predict(dev['x'][0]);a2,_=load(folder).predict(dev['x'][0]);np.testing.assert_array_equal(a1,a2)
        models.append(dict(seed=seed,selected_epoch=meta['selected_epoch'],selected_tensors_dev_regret=metrics['dev_regret'],inference_input_dimensions=20,actual_future_noise_inference=False))
    (a.run/'model-verification.json').write_text(json.dumps(dict(verified=True,models=models,ppo_finetuning=False),indent=2)+'\n')
    print('All3 saved students reproduce selected DEV regret and normalization.')


if __name__=='__main__':main()
