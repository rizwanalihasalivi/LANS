import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parent/'revision2')]
from mapping import legacy_units,RangeMappedPolicy,map_worker_packet
from matched_env import MatchedResidualEnv,module
from comparison import configure_lqr
from tracking import tracking_lqr
from gating import Gate

class RangeContracts(unittest.TestCase):
    def setUp(self):configure_lqr()
    def test_endpoints_and_invalid(self):
        np.testing.assert_allclose(legacy_units([-2.,-1.,0.,1.,2.])*.5,[-.08,-.08,0,.08,.08],atol=1e-8)
        with self.assertRaises(ValueError):legacy_units([np.nan])
    def test_training_dynamics_reward_parity(self):
        for value in [-1.,0.,1.]:
            env=MatchedResidualEnv(111);legacy=module.SurvivalEnv('residual',111)
            a,_=env.reset();b,_=legacy.reset();np.testing.assert_array_equal(a,b)
            baseline=tracking_lqr(env.estimate,env.speed,env.kappa)
            a,ra,ta,xa,info=env.step(np.array([value]));b,rb,tb,xb,_=legacy.step(np.array([value*.16]))
            np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(env.state,legacy.state)
            self.assertEqual((ra,ta,xa),(rb,tb,xb));self.assertAlmostEqual(info['requested_residual_rad'],value*.08)
            self.assertAlmostEqual(env.last_command,np.clip(baseline+value*.08,-.5,.5))
    def test_evaluation_and_worker_units_agree(self):
        class Model:
            def predict(self,obs,deterministic=True):return np.array([obs]),None
        wrapped=RangeMappedPolicy(Model())
        for value in [-1.,-.5,0.,.5,1.]:
            action,_=wrapped.predict(value);packet=map_worker_packet(dict(sequence=3,angle_rad=value*.5,t_observation_s=2.))
            self.assertAlmostEqual(float(action[0])*.5,value*.08)
            self.assertAlmostEqual(packet['angle_rad'],value*.08)
            self.assertEqual(packet['sequence'],3);self.assertEqual(packet['t_observation_s'],2.)
        self.assertIsNone(map_worker_packet(None))
    def test_gate_preserves_range_and_stale_fallback(self):
        from core import GAINS
        gate=Gate({'horizon_steps':20,'relative_margin':.01});state=np.zeros(4)
        for action in [-1.,1.]:
            output=(1,.1,float(legacy_units([action])[0])*.5)
            for _ in range(10):
                command,weight,reason,*_=gate.choose(.1,.02,output,state,0.,20.,0.,GAINS[20],'residual')
                self.assertLessEqual(abs(command-.02),weight*.08+1e-12)
            self.assertEqual(gate.choose(.2,.02,output,state,0.,20.,0.,GAINS[20],'residual')[:3],(.02,0.,'age'))
if __name__=='__main__':unittest.main()
