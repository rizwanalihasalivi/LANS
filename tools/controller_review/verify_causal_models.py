"""Verify projected TRAIN-only normalization and DEV-only checkpoint selection."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from causal_student import ROOT, project_queries, load_causal, validation, REMOVED


def main():
    p=argparse.ArgumentParser();p.add_argument('--models',type=Path,required=True);a=p.parse_args()
    torch.set_num_threads(1)
    data=ROOT/'integrations/webots/results/revision8-student/data'
    train=np.load(data/'train.npz');dev=np.load(data/'dev.npz')
    x=project_queries(train['x']);dx=project_queries(dev['x'])
    mean=x.mean(0,dtype=np.float64).astype(np.float32)
    std=np.maximum(x.std(0,dtype=np.float64),.001).astype(np.float32)
    costs=dev['costs'];regret=np.clip((costs-costs.min(1,keepdims=True))/np.maximum(costs[:,2:3],1e-4),0,1)
    rows=[]
    for seed in (701,802,903):
        folder=a.models/str(seed);meta=json.loads((folder/'complete.json').read_text())
        epochs=json.loads((folder/'epochs.json').read_text())
        assert len(epochs)==20 and [r['epoch'] for r in epochs]==list(range(1,21))
        assert min(epochs,key=lambda r:r['dev_regret'])['epoch']==meta['selected_epoch']
        for name,digest in meta['source_hashes'].items():
            assert hashlib.sha256((data/name).read_bytes()).hexdigest()==digest
        norm=np.load(folder/'normalization.npz')
        np.testing.assert_array_equal(norm['mean'],mean);np.testing.assert_array_equal(norm['std'],std)
        assert np.all(mean[list(REMOVED)]==0)
        model=load_causal(folder)
        result=validation(model,torch.from_numpy(dx),dev['labels'],regret,dev['groups'])
        assert abs(result['dev_regret']-meta['best_dev_regret'])<1e-12
        rows.append(dict(seed=seed,selected_epoch=meta['selected_epoch'],**result,
            model_sha256=hashlib.sha256((folder/'student.pt').read_bytes()).hexdigest(),
            normalization_sha256=hashlib.sha256((folder/'normalization.npz').read_bytes()).hexdigest()))
    report=dict(train_only_normalization_pass=True,dev_only_selection_and_saved_model_pass=True,
        train_groups=len(np.unique(train['groups'])),dev_groups=len(np.unique(dev['groups'])),
        train_ready_packet_rows=int((train['x'][:,17]>.5).sum()),
        dev_ready_packet_rows=int((dev['x'][:,17]>.5).sum()),models=rows)
    (a.models/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
