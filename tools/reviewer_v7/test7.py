import boot7
import json
import math
import tempfile
import unittest
import numpy as np
from compensation import DelayCompensator,CompensatedController,forecast_state

class Contracts(unittest.TestCase):
    def test_zero_horizon_identity(self):
        z=np.array([.2,0,.01,0]);delta=.03;ks=np.array([.001,.002,.003]);g=np.ones(4)
        zz,dd,kk=forecast_state(z,delta,20.,ks,g,0.)
        np.testing.assert_array_equal(z,zz);np.testing.assert_array_equal(ks,kk);self.assertEqual(delta,dd)
    def test_known_straight_kinematics(self):
        z,delta,_=forecast_state([.2,0,.01,0],0.,20.,[0,0,0],[0,0,0,0],.03)
        np.testing.assert_allclose(z,[.206,0,.01,0],rtol=0,atol=1e-14);self.assertEqual(delta,0.)
    def test_independent_matrix_equations_and_fractional_step(self):
        rng=np.random.default_rng(731)
        for _ in range(200):
            z=rng.normal(size=4)*[.1,.03,.01,.02];delta=float(rng.uniform(-.1,.1));v=float(rng.uniform(15,25));h=float(rng.uniform(0,.04));ks=rng.normal(size=3)*.001;g=rng.uniform(0,.5,4)
            expected=z.copy();a=delta;elapsed=0.
            while elapsed<h-1e-12:
                dt=min(.01,h-elapsed);k=float(np.interp(v*elapsed,[0,10,20],ks));vyref=(1.4*v-1650*1.2*v**3/(2.6*80000))*k
                ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*v*v)*k
                u=np.clip(ff-g@(expected-np.array([0,vyref,-vyref/v,v*k])),-.5,.5);a+=dt*np.clip((u-a)/.05,-.35,.35)
                A=np.array([[0,1,v,0],[0,-160000/(1650*v),0,16000/(1650*v)-v],[0,0,0,1],[0,16000/(4224*v),0,-80000*(1.2**2+1.4**2)/(4224*v)]])
                expected+=dt*(A@expected+np.array([0,80000/1650,0,96000/4224])*a+np.array([0,0,-v*k,0]));elapsed+=dt
            actual,aa,_=forecast_state(z,delta,v,ks,g,h)
            np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-13);self.assertAlmostEqual(a,aa,14)
    def test_completed_history_only_no_repeated_age_updates(self):
        c=DelayCompensator();self.assertEqual(c.delay_s,.01)
        self.assertTrue(c.observe(1,.03));self.assertAlmostEqual(c.delay_s,.015)
        self.assertFalse(c.observe(1,.04));self.assertFalse(c.observe(0,.04));self.assertEqual(c.samples,1)
        with self.assertRaises(ValueError):c.observe(2,-.01)
        for i in range(2,100):c.observe(i,1.)
        self.assertLessEqual(c.delay_s,.04)
    def test_predict_physics_keep_known_history_and_future_zeros(self):
        raw=np.zeros(20,np.float32);raw[9:15]=[.1,.2,.3,.4,1,.5];raw[18]=.3
        out,meta=DelayCompensator().prepare(raw,[.2,0,.01,0],0.,20.,[0,0,0],[0,0,0,0])
        self.assertNotEqual(out[0],raw[0]);np.testing.assert_array_equal(out[9:],raw[9:]);self.assertEqual(meta['completed_history_samples'],0)
        self.assertEqual(meta['used_horizon_s'],.01)
    def test_no_freshness_reset(self):
        c=CompensatedController();c.packet=(1,0.,.04);original=c.packet
        c.prepare_query(np.zeros(20,np.float32),[.2,0,.01,0],0.,20.,[0,0,0],[0,0,0,0])
        command,reason=c.choose(.05,.1,np.zeros(4),0.,20.,0.,np.zeros(4))
        self.assertEqual(c.packet,original);self.assertEqual(reason,'age');self.assertEqual(command,.1);self.assertEqual(c.weight,0.)
    def test_envelope_failure_falls_back_to_actual_features(self):
        raw=np.zeros(20,np.float32);out,m=DelayCompensator().prepare(raw,[2.,0,0,0],0.,20.,[0,0,0],[0,0,0,0])
        np.testing.assert_array_equal(out,raw);self.assertEqual(m['used_horizon_s'],0.)
    def test_runtime_abi_guard(self):
        from laptop_full_controller import episode
        with tempfile.TemporaryDirectory() as d:
            folder=boot7.Path(d);(folder/'manifest.json').write_text(json.dumps({'profile':'causal_filter_history_v5'}))
            with self.assertRaises(ValueError):episode(None,'nominal',701,'delay_compensated',1,folder,folder)

if __name__=='__main__':unittest.main()
