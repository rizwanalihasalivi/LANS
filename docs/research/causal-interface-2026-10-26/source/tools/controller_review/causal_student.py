"""Causal query-time v2 profile: no pending result, completion forecast or service oracle.

Reuse only the frozen v8 TRAIN/DEV labels. No final-evaluation data is consumed.
At an available-worker query, a ready simulated packet is delivered first; this
is observable at query time. Pending features are then removed in train and run.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'integrations/webots/research/revision8'))
from student import Student, validation

PROFILE='causal_query_v2'
REMOVED=(14,15,16,17,19)


def project_queries(source):
    x=np.asarray(source,dtype=np.float32).copy()
    if x.ndim!=2 or x.shape[1]!=20 or not np.isfinite(x).all():
        raise ValueError('finite 20-channel rows required')
    # The archived collector queries only when its worker is available.
    # A ready pending packet is now observable and becomes the held packet.
    ready=x[:,17]>.5
    if np.any(x[ready,15]>1e-6):
        raise ValueError('query includes unavailable future packet')
    x[ready,11]=x[ready,14]
    x[ready,12]=x[ready,16]
    x[ready,13]=1.
    x[:,REMOVED]=0.
    return x


def runtime_features(*args,**kwargs):
    # Native queries are issued after polling, only when the worker is idle.
    from realtime_student import causal_features
    obs=causal_features(*args,**kwargs)
    obs[list(REMOVED)]=0.
    return obs


class CausalStudent(Student):
    def predict(self,observation,deterministic=True):
        x=np.asarray(observation,dtype=np.float32)
        if x.shape!=(20,) or not np.isfinite(x).all() or np.any(x[list(REMOVED)]!=0):
            raise ValueError('causal-query-v2 features required; oracle channels must be zero')
        return super().predict(x,deterministic=deterministic)


def load_causal(folder):
    folder=Path(folder);meta=json.loads((folder/'complete.json').read_text())
    if meta['profile']!=PROFILE:raise ValueError('profile mismatch')
    norm=np.load(folder/'normalization.npz')
    model=CausalStudent(norm['mean'],norm['std'])
    model.load_state_dict(torch.load(folder/'student.pt',map_location='cpu'));model.eval()
    return model


def train(seed,output,epochs=20):
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.manual_seed(seed);np.random.seed(seed)
    output.mkdir(parents=True,exist_ok=False)
    data=ROOT/'integrations/webots/results/revision8-student/data'
    train=np.load(data/'train.npz');dev=np.load(data/'dev.npz')
    x=project_queries(train['x']);dx=project_queries(dev['x'])
    assert len(np.unique(train['groups']))==216 and len(np.unique(dev['groups']))==108
    mean=x.mean(0,dtype=np.float64).astype(np.float32)
    std=np.maximum(x.std(0,dtype=np.float64),.001).astype(np.float32)
    np.savez(output/'normalization.npz',mean=mean,std=std)
    model=CausalStudent(mean,std);optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    costs=train['costs'];labels=train['labels']
    regret=np.clip((costs-costs.min(1,keepdims=True))/np.maximum(costs[:,2:3],1e-4),0,1).astype(np.float32)
    dc=dev['costs'];dr=np.clip((dc-dc.min(1,keepdims=True))/np.maximum(dc[:,2:3],1e-4),0,1)
    tx=torch.from_numpy(x);ty=torch.from_numpy(labels).long();tr=torch.from_numpy(regret)
    useful=labels!=2;n=int(useful.sum())
    weights=np.ones(len(x)) if n in (0,len(x)) else np.where(useful,.5/n,.5/(len(x)-n))
    weights=torch.from_numpy(weights);history=[];best=float('inf');selected=None
    for epoch in range(1,epochs+1):
        model.train();indices=torch.multinomial(weights,len(x),replacement=True)
        for batch in indices.split(256):
            logits=model(tx[batch])
            loss=nn.functional.cross_entropy(logits,ty[batch])+(logits.softmax(1)*tr[batch]).sum(1).mean()
            optimizer.zero_grad();loss.backward();optimizer.step()
        model.eval();stats=validation(model,torch.from_numpy(dx),dev['labels'],dr,dev['groups'])
        row=dict(epoch=epoch,**stats);history.append(row)
        if stats['dev_regret']<best:
            best=stats['dev_regret'];selected=epoch;torch.save(model.state_dict(),output/'student.pt')
        print(seed,epoch,stats['dev_regret'],flush=True)
    (output/'epochs.json').write_text(json.dumps(history,indent=2)+'\n')
    meta=dict(profile=PROFILE,seed=seed,selected_epoch=selected,epochs_executed=epochs,
        best_dev_regret=best,train_rows=len(x),dev_rows=len(dx),normalization_fit='projected TRAIN only',
        removed_channels=list(REMOVED),source_hashes={name:hashlib.sha256((data/name).read_bytes()).hexdigest() for name in ('train.npz','dev.npz')})
    (output/'complete.json').write_text(json.dumps(meta,indent=2)+'\n')
    saved=load_causal(output)
    with torch.no_grad():
        # Reload parity and inference contract, not an unseen-data performance test.
        state=model.state_dict();saved.load_state_dict(torch.load(output/'student.pt',map_location='cpu'))
        for obs in dx[:100]:saved.predict(obs)
    return meta


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,choices=[701,802,903],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();train(a.seed,a.output)
