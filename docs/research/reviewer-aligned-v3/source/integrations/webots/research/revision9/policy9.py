"""Exact five-logit actor transfer, with preprocessing serialized inside PPO."""
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from bootstrap import HERE,RESEARCH
P=json.loads((HERE/'protocol.json').read_text())


class FrozenStudent(nn.Module):
    def __init__(self,folder):
        super().__init__();meta=json.loads((folder/'complete.json').read_text())
        assert meta['profile']=='supervised_grid_v8' and meta['observation_dimensions']==20
        assert meta['protocol']['candidates_rad']==P['candidates_rad']
        norm=np.load(folder/'normalization.npz')
        self.register_buffer('mean',torch.as_tensor(norm['mean'],dtype=torch.float32))
        self.register_buffer('std',torch.as_tensor(norm['std'],dtype=torch.float32))
        self.net=nn.Sequential(nn.Linear(20,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh(),nn.Linear(64,5))
        self.load_state_dict(torch.load(folder/'student.pt',map_location='cpu'));self.eval()
    def forward(self,x):return self.net((x-self.mean)/self.std)
    def predict(self,observation,deterministic=True):
        value=np.asarray(observation,dtype=np.float32)
        if value.shape!=(20,) or not np.isfinite(value).all():raise ValueError('20 finite observed inputs required')
        with torch.no_grad():index=int(self(torch.from_numpy(value)[None]).argmax(1).item())
        return np.array([P['candidates_rad'][index]/.08],dtype=np.float32),None


class ObservedStandardizer(BaseFeaturesExtractor):
    def __init__(self,observation_space,mean,std):
        super().__init__(observation_space,features_dim=20)
        if observation_space.shape!=(20,):raise ValueError('20-feature interface required')
        self.register_buffer('mean',torch.as_tensor(mean,dtype=torch.float32))
        self.register_buffer('std',torch.as_tensor(std,dtype=torch.float32))
    def forward(self,observations):return (observations-self.mean)/self.std


def copy_actor(model,student):
    with torch.no_grad():
        for source,target in [(student.net[0],model.policy.mlp_extractor.policy_net[0]),
                              (student.net[2],model.policy.mlp_extractor.policy_net[2]),
                              (student.net[4],model.policy.action_net)]:
            target.weight.copy_(source.weight);target.bias.copy_(source.bias)


def logits(model,observations):
    return model.policy.action_net(model.policy.mlp_extractor.forward_actor(model.policy.extract_features(observations)))


class PPOAdapter:
    def __init__(self,model):
        if model.observation_space.shape!=(20,) or getattr(model.action_space,'n',None)!=5:raise ValueError('categorical5 PPO required')
        self.model=model
    def predict(self,observation,deterministic=True):
        value=np.asarray(observation,dtype=np.float32)
        if value.shape!=(20,) or not np.isfinite(value).all():raise ValueError('20 finite observed inputs required')
        action,_=self.model.predict(value,deterministic=deterministic);index=int(np.asarray(action).item())
        if not 0<=index<5:raise ValueError('invalid categorical action')
        return np.array([P['candidates_rad'][index]/.08],dtype=np.float32),None
