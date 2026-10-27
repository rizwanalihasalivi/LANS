import boot
import unittest
from unittest.mock import patch
import numpy as np
from filtered import FilteredController,rate_cost
from nominal_psf import NominalPSF


class Contracts(unittest.TestCase):
    def test_filter_causal_and_immediate_stale_reset(self):
        c=FilteredController('age_filtered');c.submit(0.,.08,0.)
        command,_=c.choose(0.,0.,np.zeros(4),0.,20.,0.,np.ones(4))
        self.assertAlmostEqual(c.filtered,(1-np.exp(-.1))*.08)
        self.assertAlmostEqual(command,.25*c.filtered)
        self.assertEqual(c.choose(.05,.03,np.zeros(4),0.,20.,0.,np.ones(4)),(.03,'age'))
        self.assertEqual(c.filtered,0.)

    def test_valid_filter_history_survives_cost_rejection(self):
        c=FilteredController('predictive_filtered');c.submit(0.,.08,0.)
        with patch('filtered.rate_cost',return_value=1.):
            self.assertEqual(c.choose(0.,0.,np.zeros(4),0.,20.,0.,np.ones(4))[1],'cost')
        self.assertGreater(c.filtered,0.);self.assertEqual(c.weight,0.)

    def test_rate_predictor_mirrors(self):
        z=np.array([.15,.01,.02,.03]);g=np.array([.2,.1,.3,.1]);ks=np.array([.001,.002,-.001])
        self.assertAlmostEqual(rate_cost(z,.01,.02,20.,.001,g,ks,True),
                               rate_cost(-z,-.01,-.02,20.,-.001,g,-ks,True),places=12)

    def test_psf_feasible_and_constraint_checked(self):
        psf=NominalPSF();value,status=psf.command(np.zeros(4),0.,20.,0.,.01,0.,1)
        self.assertEqual(status,'full_feasible');self.assertLessEqual(psf.last_violation,1e-4)
        self.assertAlmostEqual(value,.01,delta=.001)

    def test_psf_shrinks_after_infeasible_full_horizon(self):
        psf=NominalPSF();psf.last_full=10
        with patch.object(psf,'solve',side_effect=[None,.02]) as solve:
            value,status=psf.command(np.zeros(4),0.,20.,0.,.01,0.,20)
        self.assertEqual((value,status),(.02,'shortened_feasible'))
        self.assertEqual([args.args[-1] for args in solve.call_args_list],[100,90])


if __name__=='__main__':unittest.main()
