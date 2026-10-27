import boot8
import math
import unittest
from unittest.mock import patch
import numpy as np
from recovery8 import RecoveryController
from scalar_cost import scalar_cost
from expiry_cost8 import expiry_cost

class Recovery(unittest.TestCase):
    def controller(self):
        c=RecoveryController();c.previews=np.zeros(3);return c
    def choose(self,c,t,seq,observed=None,residual=.04):
        c.packet=(seq,t-.04 if observed is None else observed,residual)
        with patch('recovery8.expiry_cost',side_effect=lambda *a:1. if a[-2]==0 else .9):
            return c.choose(t,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
    def test_40ms_three_distinct_proposals_recover(self):
        c=self.controller()
        for i,t in enumerate((.04,.08,.12),1):
            _,reason=self.choose(c,t,i)
            self.assertEqual(c.good,i)
            if i<3:self.assertEqual(reason,'recovery')
            else:self.assertEqual(reason,'accepted');self.assertGreater(c.weight,0.)
            command,reason=c.choose(t+.01,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
            self.assertEqual(reason,'age');self.assertEqual(c.weight,0.);self.assertEqual(command,0.);self.assertEqual(c.good,i)
    def test_held_packet_cannot_count_three_times(self):
        c=self.controller()
        for t in (.01,.02,.03):self.choose(c,t,1,observed=0.)
        self.assertEqual(c.good,1);self.assertEqual(c.weight,0.)
    def test_evidence_expires_without_distinct_response(self):
        c=self.controller();self.choose(c,.04,1)
        c.choose(.091,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
        self.assertEqual(c.good,0);self.assertEqual(c.filtered,0.);self.assertIsNone(c.last_qualified_time)
    def test_missing_invalid_and_cost_reset(self):
        for mode in ('missing','invalid','cost'):
            c=self.controller();self.choose(c,.04,1)
            if mode=='missing':c.packet=None;c.choose(.05,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
            elif mode=='invalid':self.choose(c,.05,2,observed=.04,residual=.1)
            else:
                c.packet=(2,.04,.04)
                with patch('recovery8.expiry_cost',return_value=1.):c.choose(.05,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
            self.assertEqual(c.good,0);self.assertEqual(c.weight,0.)
    def test_expiry_predictor_limits(self):
        rng=np.random.default_rng(831)
        for _ in range(200):
            args=(rng.normal(size=4)*[.2,.1,.02,.03],float(rng.uniform(-.1,.1)),20.,rng.normal(size=3)*.001,np.array([.2,.1,.3,.1]),.01,.04,.15)
            full=expiry_cost(*args,100);old=scalar_cost(*args)
            self.assertAlmostEqual(full,old,11)
            self.assertAlmostEqual(expiry_cost(*args,0),expiry_cost(*args[:-1],0.,0),11)
    def test_stale_and_future_never_admitted(self):
        c=self.controller()
        for t,observed in ((.05,0.),(.01,.02),(1.,0.)):
            command,_=self.choose(c,t,1,observed=observed)
            self.assertEqual(command,0.);self.assertEqual(c.weight,0.)
    def test_budget_boundary_and_hard_revoke(self):
        from laptop_full_controller import budget_due,runtime_revoke
        self.assertFalse(budget_due(0,8999999));self.assertTrue(budget_due(0,9000000));self.assertTrue(budget_due(0,10000000))
        c=self.controller();self.choose(c,.04,1)
        runtime_revoke(c,0.,'age',clear=False);self.assertEqual(c.good,1);self.assertEqual(c.weight,0.)
        runtime_revoke(c,0.,'budget');self.assertEqual(c.good,0);self.assertIsNone(c.last_qualified_time)
    def test_prediction_never_assumes_post_expiry_assistance(self):
        for age,steps in ((0.,5),(.01,4),(.02,3),(.04,1),(.049,1)):
            c=self.controller();c.packet=(1,0.,.04);seen=[]
            def cost(*args):seen.append(args[-1]);return 1. if args[-2]==0 else .9
            with patch('recovery8.expiry_cost',side_effect=cost):c.choose(age,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
            self.assertEqual(seen,[0,steps])

if __name__=='__main__':unittest.main()
