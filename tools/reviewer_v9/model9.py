import boot9
import numpy as np
import torch
from torch import nn
from features9 import NEW

class Bridge(nn.Module):
    def __init__(self,kind,pair):
        super().__init__();seed=(701,802,903)[pair]
        if kind=='student':
            import sys
            sys.path.insert(0,str(boot9.ROOT/'tools/reviewer_v5'))
            from history5 import Bridge as Old
            old=Old('student',pair);mean=old.mean.clone();std=old.std.clone();self.net=old.net
        else:
            with np.load(boot9.ROOT/f'docs/research/reviewer-history-v5/portable-actor/model-{seed}.npz',allow_pickle=False) as z:
                mean=torch.from_numpy(z['mean'].copy());std=torch.from_numpy(z['std'].copy())
                self.net=nn.Sequential(nn.Linear(20,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh(),nn.Linear(64,5))
                with torch.no_grad():
                    for i,layer in enumerate((self.net[0],self.net[2],self.net[4])):layer.weight.copy_(torch.from_numpy(z[f'w{i}'].T.copy()));layer.bias.copy_(torch.from_numpy(z[f'b{i}'].copy()))
        with torch.no_grad():mean[list(NEW)]=0.;std[list(NEW)]=1.;self.net[0].weight[:,list(NEW)]=0.
        self.register_buffer('mean',mean);self.register_buffer('std',std)
    def forward(self,x):return self.net((x-self.mean)/self.std)
