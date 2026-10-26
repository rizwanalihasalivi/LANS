import copy,unittest
import numpy as np
from bootstrap import RESEARCH
from comparison import configure_lqr
from core import GAINS
from matched_env import MatchedResidualEnv
from env4 import ResearchEnv
from reward_model import relative_bonus

class Contracts(unittest.TestCase):
    def setUp(self):configure_lqr()
    def test_A_matches_existing_baseline(self):
        new=ResearchEnv('A',101);old=MatchedResidualEnv(101)
        a,_=new.reset();b,_=old.reset();np.testing.assert_array_equal(a,b)
        for action in [0.,.3,-.7,1.,-.2]*3:
            a,ra,ta,xa,ia=new.step(np.array([action],dtype=np.float32));b,rb,tb,xb,ib=old.step(np.array([action],dtype=np.float32))
            np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(new.state,old.state)
            self.assertAlmostEqual(ra,rb,places=14);self.assertEqual((ta,xa),(tb,xb))
    def test_training_gate_is_actual_frozen_gate(self):
        env=ResearchEnv('B',101);env.reset()
        for _ in range(15):
            gate=copy.deepcopy(env.gate);s=env.state.copy();est=env.estimate.copy();k=env.kappa;t=env.steps*.01
            from tracking import tracking_lqr
            baseline=tracking_lqr(est,env.speed,k)
            expected=gate.choose(t,baseline,(env.steps+1,t,.04),est,s[5],env.speed,k,GAINS[env.speed],'residual')
            _,_,_,_,info=env.step(np.array([.5]))
            self.assertEqual((info['command'],info['gate_weight'],info['gate_reason']),expected[:3])
    def test_zero_action_or_rejection_has_zero_relative_bonus(self):
        for arm in ['C','D']:
            env=ResearchEnv(arm,101);env.reset();_,_,_,_,info=env.step(np.array([0.]))
            self.assertEqual(info['relative_bonus'],0.);self.assertEqual(info['lqr_cost'],info['executed_cost'])
        env=ResearchEnv('D',101);env.reset();env.estimate[0]=2.
        _,_,_,_,info=env.step(np.array([1.]))
        self.assertEqual(info['gate_weight'],0.);self.assertEqual(info['relative_bonus'],0.)
    def test_counterfactual_is_nonmutating_and_symmetric(self):
        env=ResearchEnv('C',101);env.reset();before=env.state.copy();rng=copy.deepcopy(env.sensor.rng.bit_generator.state)
        a,j0,j1=relative_bonus(env.state,.02,-.01,env.speed,env.path,.7,.8,GAINS[env.speed])
        b,k0,k1=relative_bonus(env.state,-.01,.02,env.speed,env.path,.7,.8,GAINS[env.speed])
        self.assertEqual(j0,k1);self.assertEqual(j1,k0);self.assertLessEqual(a*b,0)
        np.testing.assert_array_equal(env.state,before);self.assertEqual(rng,env.sensor.rng.bit_generator.state)
    def test_randomization_bounds_reproducibility_and_hidden_parameters(self):
        a=ResearchEnv('D',202);b=ResearchEnv('D',202);domains=[]
        for _ in range(30):
            oa,_=a.reset();ob,_=b.reset();np.testing.assert_array_equal(oa,ob);self.assertEqual(oa.shape,(9,))
            self.assertEqual((a.mu,a.stiffness,a.noise,a.delay),(b.mu,b.stiffness,b.noise,b.delay))
            self.assertTrue(.6<=a.mu<=.9 and .65<=a.stiffness<=1 and 1<=a.noise<=2 and a.delay in [0,1]);domains.append(a.randomized)
        self.assertTrue(any(domains) and not all(domains))
if __name__=='__main__':unittest.main()
