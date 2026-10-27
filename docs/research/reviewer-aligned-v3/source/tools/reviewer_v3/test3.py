import boot3
import unittest
from unittest.mock import patch
import math
import numpy as np
from aligned import AlignedController,AlignedEnv,trajectory_cost


class Contracts(unittest.TestCase):
    def test_prediction_mirror_and_longer_horizon(self):
        z=np.array([.15,.01,.02,.03]);g=np.array([.2,.1,.3,.1]);ks=np.array([.001,.002,-.001])
        a=trajectory_cost(z,.01,20.,ks,g,.01,.04,.25)
        b=trajectory_cost(-z,-.01,20.,-ks,g,-.01,-.04,.25)
        self.assertAlmostEqual(a,b,places=12);self.assertTrue(math.isfinite(a))
    def test_filter_recovery_and_immediate_stale_revoke(self):
        c=AlignedController();c.submit(0.,.08,0.)
        with patch('aligned.trajectory_cost',side_effect=[1.,.9]*3):
            for i in range(3):u,reason=c.choose(i*.01,.01,np.zeros(4),0.,20.,0.,np.ones(4))
        self.assertEqual(reason,'accepted');self.assertAlmostEqual(c.filtered,.08*(1-math.exp(-.03/.3)))
        self.assertAlmostEqual(u,.01+c.weight*c.filtered)
        self.assertEqual(c.choose(.05,.03,np.zeros(4),0.,20.,0.,np.ones(4)),(.03,'age'))
        self.assertEqual((c.filtered,c.weight,c.good),(0.,0.,0))
    def test_execution_reward_is_actual_rate_not_command_jump(self):
        e=AlignedEnv(case=(20,'dlc220',1,'nominal',1306000401));e.reset()
        _,reward,_,_,r=e.step(4)
        expected=-(r['lateral_error']/.5)**2-.2*(r['heading_error']/.1)**2-.2*(r['steering_rate']/.35)**2-.005*(r['command']/.5)**2-10*r['failed']
        self.assertAlmostEqual(reward,expected,places=12)
        self.assertTrue(np.all(e.obs[[14,15,16,17,19]]==0));self.assertIsInstance(e.ctrl,AlignedController)
    def test_one_second_worker_does_not_delay_local_lqr(self):
        a=AlignedEnv(case=(20,'dlc220',1,'stall1000',1306000402));b=AlignedEnv(case=(20,'dlc220',1,'stall1000',1306000402),baseline=True)
        a.reset();b.reset()
        for _ in range(120):
            ra=a.step(4)[4];rb=b.step(2)[4]
            self.assertEqual(ra['command'],rb['command']);np.testing.assert_array_equal(a.state,b.state)
    def test_training_noise_namespace_and_causal_reset(self):
        a=AlignedEnv(seed=3701);b=AlignedEnv(seed=3701);x,info=a.reset();y,info2=b.reset()
        np.testing.assert_array_equal(x,y);self.assertEqual(info,info2)
        self.assertGreaterEqual(info['noise_id'],1306000000)
        self.assertEqual(a.ctrl.filtered,0.);self.assertTrue(np.all(x[[14,15,16,17,19]]==0))


if __name__=='__main__':unittest.main()
