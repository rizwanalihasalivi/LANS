import unittest
import numpy as np
from run import cost,choose,episode,P,RESEARCH
from teacher import choose as original_choose
from kernels import initial_executor
from comparison import configure_lqr
from core import GAINS

class Contracts(unittest.TestCase):
 def setUp(self):
  configure_lqr();self.gains=np.array([GAINS[v] for v in (15,20,25)])
  self.state=np.array([0.,.15,.01,0.,0.,0.]);self.estimate=np.array([.15,0.,.01,0.]);self.cov=np.eye(4)*.01;self.raw=np.array([.15,.01,0.,25.]);self.worker=initial_executor();self.path=(1.,0.,0.,0.);self.forecast=np.random.default_rng(7).normal(0,.001,(41,4))
 def test_hold20_matches_original_and_no_mutation(self):
  saved=self.state.copy();args=(self.state,self.estimate,self.cov,self.raw,self.worker,0)
  old,_=original_choose(*args,0,25.,self.path,.9,1.,self.forecast,0,1.,25.,0.,self.gains)
  value=choose(*args,0,0,25.,self.path,.9,1.,self.forecast,0,1.,25.,0.,self.gains)
  self.assertEqual(value,P['candidates_rad'][old]);np.testing.assert_array_equal(saved,self.state)
 def test_second_action_irrelevant_for20_and_equal_hold_symmetry(self):
  args=(self.state,self.estimate,self.cov,self.raw,self.worker,0)
  tail=(0,25.,self.path,.9,1.,self.forecast,0,1.,25.,0.,self.gains)
  a=cost(*args,.04,.08,20,*tail);b=cost(*args,.04,-.08,20,*tail)
  self.assertEqual(a,b);self.assertTrue(np.isfinite(cost(*args,.04,.04,40,*tail)))
 def test_severe_delay_equal_lqr(self):
  # No model needed for finite teacher methods.
  a=episode('lqr',0,'latency100',None,self.gains)
  for method in ['hold20','hold40','sequence40']:
   b=episode(method,0,'latency100',None,self.gains)
   self.assertEqual(a['penalized_rmse'],b['penalized_rmse']);self.assertEqual(b['active_fraction'],0.)

if __name__=='__main__':unittest.main()
