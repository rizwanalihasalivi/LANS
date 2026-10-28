import boot11
import unittest
import torch
import pickle
import numpy as np
from env11 import Env,P
from train11 import initialize
from stable_baselines3 import PPO

class Contracts(unittest.TestCase):
    def test_full_continuation_state_preserved(self):
        model,env,old,updates=initialize(0);original=PPO.load(old/'policy.zip',device='cpu')
        for name,value in original.policy.state_dict().items():torch.testing.assert_close(value,model.policy.state_dict()[name],rtol=0,atol=0)
        a=original.policy.optimizer.state_dict();b=model.policy.optimizer.state_dict();self.assertEqual(a['param_groups'],b['param_groups'])
        for key,state in a['state'].items():
            for k,v in state.items():
                if isinstance(v,torch.Tensor):torch.testing.assert_close(v,b['state'][key][k],rtol=0,atol=0)
                else:self.assertEqual(v,b['state'][key][k])
        
        with (old/'reward-normalization.pkl').open('rb') as file:previous_norm=pickle.load(file)
        self.assertEqual(env.ret_rms.mean,previous_norm.ret_rms.mean);self.assertEqual(env.ret_rms.var,previous_norm.ret_rms.var);self.assertEqual(env.ret_rms.count,previous_norm.ret_rms.count)
        self.assertEqual(updates,original._n_updates);self.assertEqual(model.seed,P['training_seeds'][0]);self.assertFalse(env.norm_obs);env.close()
    def test_fresh_training_namespace_and_seed(self):
        a=Env(pair=0,slot=0,seed=7701,source='newppo_rk');b=Env(pair=0,slot=0,seed=7701,source='newppo_rk');x,_=a.reset();y,_=b.reset()
        np.testing.assert_array_equal(x,y);np.testing.assert_array_equal(a.noise,b.noise);self.assertEqual(a.noise_id,P['training_noise_base']);self.assertFalse(np.any(x[[16,17]]))
    def test_terminal_observation_is_updated(self):
        e=Env(source='newppo_rk',case=(20,'dlc220',1,'nominal',1726099999),scenario='nominal');x,_=e.reset();e.horizon=1;y,_,_,done,_=e.step_residual(0.)
        self.assertTrue(done);self.assertFalse(np.array_equal(x,y));self.assertEqual(y[13],1.)
if __name__=='__main__':torch.set_num_threads(1);unittest.main()
