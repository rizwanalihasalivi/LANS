import numpy as np
import torch
from stable_baselines3 import PPO
from .core import ROOT,Env
from .train import initialize


def test_original_actor_columns_survive_observation_expansion():
    env=Env()
    try:
        new,origin,_=initialize(42,env);old=PPO.load(origin,device='cpu')
        a=new.policy.state_dict()['mlp_extractor.policy_net.0.weight']
        b=old.policy.state_dict()['mlp_extractor.policy_net.0.weight']
        torch.testing.assert_close(a[:,:17],b,rtol=0,atol=0)
        assert a.shape[0]==b.shape[0] and not a[:,17:].any()
        obs=np.linspace(-1,1,30,dtype=np.float32)
        x,_=new.predict(obs,deterministic=True);y,_=old.predict(obs[:17],deterministic=True)
        np.testing.assert_allclose(x,y,rtol=0,atol=1e-7)
    finally:env.close()
