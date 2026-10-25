"""Sensor/history-only five-class supervised policy; no hidden inputs at inference."""
import argparse,csv,json,random,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from bootstrap import HERE
P=json.loads((HERE/'protocol.json').read_text())


class Student(nn.Module):
    def __init__(self,mean,std):
        super().__init__();self.register_buffer('mean',torch.as_tensor(mean,dtype=torch.float32))
        self.register_buffer('std',torch.as_tensor(std,dtype=torch.float32))
        self.net=nn.Sequential(nn.Linear(20,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh(),nn.Linear(64,5))
    def forward(self,x):return self.net((x-self.mean)/self.std)
    def predict(self,observation,deterministic=True):
        value=np.asarray(observation,dtype=np.float32)
        if value.shape!=(20,) or not np.isfinite(value).all():raise ValueError('20 finite observed features required')
        with torch.no_grad():index=int(self(torch.from_numpy(value).unsqueeze(0)).argmax(1).item())
        return np.array([P['candidates_rad'][index]/.08],dtype=np.float32),None


def load(folder):
    meta=json.loads((folder/'complete.json').read_text())
    if meta['profile']!='supervised_grid_v8' or meta['observation_dimensions']!=20:raise ValueError('incompatible student profile')
    norm=np.load(folder/'normalization.npz');model=Student(norm['mean'],norm['std'])
    model.load_state_dict(torch.load(folder/'student.pt',map_location='cpu'));model.eval()
    return model


def validation(model,x,labels,regret,groups):
    with torch.no_grad():
        prediction=torch.cat([model(batch).argmax(1) for batch in x.split(4096)]).numpy()
    values=regret[np.arange(len(prediction)),prediction]
    group_regret=np.bincount(groups,weights=values)/np.bincount(groups)
    useful=labels!=2
    return dict(dev_regret=float(np.mean(group_regret)),accuracy=float(np.mean(prediction==labels)),
        nonzero_label_accuracy=float(np.mean(prediction[useful]==labels[useful])) if useful.any() else None)


def train(data,seed,out):
    if seed not in P['student']['seeds']:raise ValueError(seed)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)
    out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    assert json.loads((data/'complete.json').read_text())['protocol']==P
    source=np.load(data/'train.npz');dev=np.load(data/'dev.npz')
    x=source['x'];labels=source['labels'];costs=source['costs'];groups=dev['groups']
    assert x.ndim==2 and x.shape[1]==20 and dev['x'].shape[1]==20
    assert len(np.unique(source['groups']))==216 and len(np.unique(groups))==108
    assert np.isfinite(x).all() and np.isfinite(costs).all() and np.isfinite(dev['x']).all() and np.isfinite(dev['costs']).all()
    mean=x.mean(0,dtype=np.float64).astype(np.float32);std=np.maximum(x.std(0,dtype=np.float64),.001).astype(np.float32)
    np.savez(out/'normalization.npz',mean=mean,std=std)
    model=Student(mean,std);optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    regret=np.clip((costs-costs.min(1,keepdims=True))/np.maximum(costs[:,2:3],1e-4),0,1).astype(np.float32)
    dc=dev['costs'];dev_regret=np.clip((dc-dc.min(1,keepdims=True))/np.maximum(dc[:,2:3],1e-4),0,1)
    tx=torch.from_numpy(x);ty=torch.from_numpy(labels).long();tr=torch.from_numpy(regret);dx=torch.from_numpy(dev['x'])
    informative=labels!=2;n=int(informative.sum())
    weights=np.ones(len(x)) if n in (0,len(x)) else np.where(informative,.5/n,.5/(len(x)-n))
    weights=torch.from_numpy(weights);history=[];best=float('inf');selected_epoch=None
    for epoch in range(1,21):
        model.train();indices=torch.multinomial(weights,len(x),replacement=True);total=0.
        for batch in indices.split(256):
            logits=model(tx[batch]);loss=nn.functional.cross_entropy(logits,ty[batch])+(logits.softmax(1)*tr[batch]).sum(1).mean()
            optimizer.zero_grad();loss.backward();optimizer.step();total+=float(loss.item())*len(batch)
        model.eval();stats=validation(model,dx,dev['labels'],dev_regret,groups)
        row=dict(epoch=epoch,train_loss=total/len(x),**stats);history.append(row)
        if stats['dev_regret']<best:
            best=stats['dev_regret'];selected_epoch=epoch;torch.save(model.state_dict(),out/'student.pt')
        (out/'progress.json').write_text(json.dumps(row,indent=2)+'\n')
        print(seed,epoch,stats['dev_regret'],flush=True)
    with (out/'epochs.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=history[0],lineterminator='\n');writer.writeheader();writer.writerows(history)
    metadata=dict(profile='supervised_grid_v8',seed=seed,observation_dimensions=20,residual_scale_rad=.08,
        selected_epoch=selected_epoch,epochs_executed=20,train_rows=len(x),dev_rows=len(dx),best_dev_regret=best,
        normalization_fit='train only',student_hidden_state_inputs=False,actual_future_noise_used=False,
        wall_s=time.perf_counter()-start,protocol=P)
    (out/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    train(a.data,a.seed,a.output)
