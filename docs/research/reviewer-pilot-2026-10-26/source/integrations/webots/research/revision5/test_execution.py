import unittest
import numpy as np
from execution import Execution,matched_lqr
from execution_env import ExecutionEnv
from gating import Gate
from core import GAINS


class Contracts(unittest.TestCase):
    def test_same_gate_fusion_recovery(self):
        executor=Execution();gate=Gate({'horizon_steps':20,'relative_margin':.01})
        estimate=np.array([.2,0.,.01,0.]);base,gain=matched_lqr(estimate,25.,.001)
        for i in range(40):
            t=i*.01;action=.08 if i<20 else -.08
            a,info=executor.step(t,action,0,base,estimate,0.,25.,.001,gain)
            b,w,reason,j0,j1=gate.choose(t,base,(i+1,t,action),estimate,0.,25.,.001,gain,'residual')
            self.assertEqual(a,b);self.assertEqual(info['gate_reason'],reason);self.assertEqual(info['gate_weight'],w)

    def test_delayed_packet_identity_and_fallback(self):
        e=Execution();z=np.zeros(4)
        for i in range(30):
            u,info=e.step(i*.01,.08 if i==0 else -.08,10,.01,z,0.,25.,0.,GAINS[25])
            self.assertEqual(u,.01);self.assertEqual(info['gate_weight'],0.)
            if i==10:
                self.assertEqual(info['executed_packet_residual'],.08)
                self.assertAlmostEqual(info['action_age_s'],.1)
        self.assertEqual(e.context(.3).shape,(10,))

    def test_reward_accounting_state_and_reproducibility(self):
        a=ExecutionEnv(seed=12,randomize=True);b=ExecutionEnv(seed=12,randomize=True)
        x,_=a.reset();y,_=b.reset();np.testing.assert_array_equal(x,y)
        self.assertEqual(x.shape,(20,))
        for i in range(30):
            previous=a.observation().copy();x,r,done,trunc,info=a.step([.5]);y,s,*_=b.step([.5])
            np.testing.assert_array_equal(x,y);self.assertEqual(r,s)
            self.assertAlmostEqual(info['controller_speed_mps'],float(previous[4])*25)
            self.assertAlmostEqual(r,sum(info[k] for k in ['reward_tracking','reward_effort','reward_change','reward_survival','reward_relative']))
            if info['gate_weight']==0:self.assertEqual(info['reward_relative'],0.)

if __name__=='__main__':unittest.main()
