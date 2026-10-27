import unittest
import numpy as np
from robust_gate import RobustGate,bank_cost
from comparison import configure_lqr
from core import GAINS
from tracking import tracking_lqr


class Contracts(unittest.TestCase):
    def test_nonmutating_and_equal_branches(self):
        configure_lqr();z=np.array([.1,.01,.002,.01]);saved=z.copy()
        a=bank_cost(z,0.,.02,25.,.001,GAINS[25],.6,.65)
        self.assertEqual(a,bank_cost(z,0.,.02,25.,.001,GAINS[25],.6,.65))
        np.testing.assert_array_equal(z,saved)

    def test_stale_invalid_and_zero_fallback(self):
        configure_lqr();g=RobustGate({'horizon_steps':20,'relative_margin':.01});z=np.zeros(4)
        for packet in [None,(1,0.,.08),(2,.1,float('nan'))]:
            u,w,*_=g.choose(.1,.02,packet,z,0.,25.,0.,GAINS[25],'residual')
            self.assertEqual(u,.02);self.assertEqual(w,0.)
        for i in range(10):
            u,w,*_=g.choose(i*.01,.02,(i,i*.01,0.),z,0.,25.,0.,GAINS[25],'residual')
            self.assertEqual(u,.02);self.assertEqual(w,0.)

    def test_earned_actions_improve_all_declared_models(self):
        configure_lqr();g=RobustGate({'horizon_steps':20,'relative_margin':.01});accepted=0
        for sign in [-1,1]:
            g=RobustGate({'horizon_steps':20,'relative_margin':.01})
            z=np.array([.03,0.,.005,0.]);base=tracking_lqr(z,25.,.001)
            for i in range(15):
                u,w,reason,*_=g.choose(i*.01,base,(i,i*.01,sign*.08),z,0.,25.,.001,GAINS[25],'residual')
                if w:
                    accepted+=1;self.assertEqual(reason,'earned')
                    for mu,stiffness in g.bank:
                        a=bank_cost(z,0.,base,25.,.001,GAINS[25],mu,stiffness)
                        b=bank_cost(z,0.,u,25.,.001,GAINS[25],mu,stiffness)
                        self.assertGreaterEqual(a-b,max(1e-7,.01*a))
        self.assertGreater(accepted,0,'test must exercise acceptance, not only fallback')

if __name__=='__main__':unittest.main()
