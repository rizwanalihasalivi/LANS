import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'integrations/webots/research'))
from causal_runtime import actor_observation,packet_ages,FastSensor,np,ReferenceFrame
from gating import Gate
from causal_student import REMOVED

class NativeContracts(unittest.TestCase):
    def test_uses_larger_age_without_refreshing_observation(self):
        packet=dict(observed_ns=1_000_000_000,observed_sim_s=10.,residual=-.04)
        original=packet.copy()
        self.assertEqual(packet_ages(packet,10.02,1_100_000_000),(10.02-10.,.1,.1))
        self.assertEqual(packet,original)
        with self.assertRaises(ValueError):packet_ages(packet,9.,1_100_000_000)
    def test_exact_training_feature_contract(self):
        gate=Gate({'horizon_steps':20,'relative_margin':.01})
        packet=dict(residual=-.04)
        obs=actor_observation(np.zeros(9),gate,packet,.02,.04)
        self.assertEqual(obs.shape,(20,));self.assertTrue(np.all(obs[list(REMOVED)]==0))
        self.assertAlmostEqual(obs[11],-.5);self.assertAlmostEqual(obs[12],.2,places=6)
        self.assertEqual(obs[13],1.)

class CoordinateContracts(unittest.TestCase):
    def test_initial_pose_matches_map_without_moving_vehicle(self):
        original=np.array([150.,3.,.07,.1,.02,.01]);saved=original.copy()
        frame=ReferenceFrame(original,(0.,2.5,120.,.3));mapped=frame.transform(original)
        self.assertAlmostEqual(mapped[0],0.)
        self.assertAlmostEqual(mapped[1],frame.reference_y)
        self.assertAlmostEqual(mapped[2],frame.reference_heading)
        np.testing.assert_array_equal(original,saved)
        np.testing.assert_array_equal(mapped[3:],original[3:])
        moved=original.copy();moved[:2]+=[4.,3.]
        transformed=frame.transform(moved)
        self.assertAlmostEqual(np.linalg.norm(transformed[:2]-mapped[:2]),5.)

if __name__=='__main__':unittest.main()
