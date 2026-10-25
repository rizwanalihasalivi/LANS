import unittest
import numpy as np
from run import branch
from comparison import configure_lqr
from core import GAINS

class Contracts(unittest.TestCase):
 def test_branch_nonmutation_python_parity_and_future_window(self):
  configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)])
  z=np.array([0.,.15,.01,0.,0.,0.]);est=np.array([.15,0.,.01,0.]);cov=np.eye(4)*.01;previous=np.array([.15,.01,0.,25.]);actual=np.random.default_rng(1).normal(0,.001,(150,4));saved=[x.copy() for x in [z,est,cov,previous,actual]]
  args=(z,est,cov,previous,0,.02,20,actual,25.,(1.,0.,0.,0.),.9,.65,1.,gains)
  a=branch(*args);b=branch.py_func(*args)
  np.testing.assert_allclose(a[:2],b[:2],rtol=1e-12);self.assertEqual(a[2],b[2])
  for before,after in zip(saved,[z,est,cov,previous,actual]):np.testing.assert_array_equal(before,after)
  actual[25:]+=1.;c=branch(*args);self.assertEqual(a,c)
 def test_identical_control_costs(self):
  configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)])
  args=(np.zeros(6),np.zeros(4),np.eye(4)*.01,np.array([0.,0.,0.,25.]),0,0.,40,np.zeros((150,4)),25.,(1.,0.,0.,0.),.9,.65,1.,gains)
  a=branch(*args);self.assertFalse(a[2]);self.assertEqual(a[:2],(0.,0.))
if __name__=='__main__':unittest.main()
