import boot6
import unittest
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure
from credit6 import CreditPPO,CreditBuffer
from history5 import HistoryEnv

class Contracts(unittest.TestCase):
    def model(self,credit=False,mask=None):
        cls=CreditPPO if credit else PPO
        m=cls('MlpPolicy','CartPole-v1',seed=918,n_steps=8,batch_size=8,n_epochs=2,ent_coef=.005,device='cpu')
        m.set_logger(configure(None,[]))
        if credit:m.rollout_buffer=CreditBuffer(8,m.observation_space,m.action_space,device='cpu',gamma=m.gamma,gae_lambda=m.gae_lambda,n_envs=1)
        rng=np.random.default_rng(813)
        for i in range(8):
            x=rng.normal(size=(1,4)).astype(np.float32)
            with torch.no_grad():act,val,log=m.policy(torch.from_numpy(x))
            if credit:m.rollout_buffer.next_credit=np.array([mask[i]])
            m.rollout_buffer.add(x,act.numpy(),np.array([rng.normal()]),np.array([i==0]),val,log)
        m.rollout_buffer.compute_returns_and_advantage(torch.zeros(1),np.array([False]))
        return m
    def test_allvalid_matches_reference_update(self):
        a=self.model();b=self.model(True,np.ones(8))
        np.random.seed(131);a.train();np.random.seed(131);b.train()
        for x,y in zip(a.policy.parameters(),b.policy.parameters()):torch.testing.assert_close(x,y,rtol=0,atol=0)
    def test_allinvalid_preserves_actor_updates_critic(self):
        m=self.model(True,np.zeros(8));before={n:p.detach().clone() for n,p in m.policy.named_parameters()}
        m.train();changed=[]
        for n,p in m.policy.named_parameters():
            if 'value' not in n:torch.testing.assert_close(p,before[n],rtol=0,atol=0)
            else:changed.append(not torch.equal(p,before[n]))
        self.assertTrue(any(changed))
    def test_discarded_advantages_have_no_actor_effect(self):
        a=self.model(True,[1,0]*4);b=self.model(True,[1,0]*4)
        b.rollout_buffer.advantages[1::2]=1e6;b.rollout_buffer.log_probs[1::2]=-99.
        np.random.seed(131);a.train();np.random.seed(131);b.train()
        for x,y in zip(a.policy.parameters(),b.policy.parameters()):torch.testing.assert_close(x,y,rtol=0,atol=0)
    def test_busy_action_does_not_change_plant(self):
        a=HistoryEnv(case=(20,'dlc220',1,'delay100',777),history=False);b=HistoryEnv(case=(20,'dlc220',1,'delay100',777),history=False)
        a.reset();b.reset();a.step_residual(.04);b.step_residual(.04)
        oa,ra,_,_,ia=a.step_residual(-.08);ob,rb,_,_,ib=b.step_residual(.08)
        self.assertFalse(ia['submitted']);self.assertFalse(ib['submitted'])
        np.testing.assert_array_equal(oa,ob);np.testing.assert_array_equal(a.state,b.state);self.assertEqual(ra,rb)

if __name__=='__main__':torch.set_num_threads(1);unittest.main()
