import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from realtime_student import Gate, causal_features, final_command
from data import G


class TimingContracts(unittest.TestCase):
    def test_expiry_during_gate_evaluation_removes_authority(self):
        gate=Gate({'horizon_steps':20,'relative_margin':.01});gate.weight=.25
        packet=dict(observed_ns=1_000_000_000)
        result=(.08,.25,'earned',1.,.9)
        self.assertEqual(final_command(gate,result,packet,1_049_999_999,.02),result)
        self.assertEqual(final_command(gate,result,packet,1_050_000_000,.02)[:3],(.02,0.,'age_at_apply'))
        self.assertEqual(gate.weight,0.)

    def test_pending_features_do_not_reveal_unknown_result_or_completion(self):
        gate=Gate({'horizon_steps':20,'relative_margin':.01})
        obs=causal_features(np.zeros(6),np.zeros(4),20.,tuple(float(v) for v in G['paths']['dlc220']),gate,
            None,True,1_000_000_000,.02,1_020_000_000)
        self.assertEqual(obs.shape,(20,));self.assertTrue(np.isfinite(obs).all())
        self.assertEqual(obs[14],0.);self.assertEqual(obs[15],0.)
        self.assertAlmostEqual(obs[16],.2,places=6);self.assertEqual(obs[17],1.)
        self.assertEqual(obs[19],0.)

    def test_original_gate_rejects_exact_deadline_future_and_invalid(self):
        gate=Gate({'horizon_steps':20,'relative_margin':.01})
        for packet in [(1,0.,.04),(1,.06,.04),(1,.05,float('nan')),None]:
            result=gate.choose(.05,.02,packet,np.zeros(4),0.,20.,0.,np.zeros(4),'residual')
            self.assertEqual(result[:2],(.02,0.))

if __name__=='__main__':unittest.main()
