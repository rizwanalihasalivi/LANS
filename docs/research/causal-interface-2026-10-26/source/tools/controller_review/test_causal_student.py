import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from causal_student import project_queries, runtime_features, CausalStudent, REMOVED
from realtime_causal import final_command, Gate
from data import G

class CausalContracts(unittest.TestCase):
    def test_future_packet_is_not_accepted_as_ready(self):
        x=np.zeros((1,20),np.float32);x[0,17]=1;x[0,15]=.2
        with self.assertRaises(ValueError):project_queries(x)

    def test_ready_delivery_training_equals_observable_runtime_context(self):
        x=np.zeros((1,20),np.float32);x[0,14]=-.5;x[0,16]=.2;x[0,17]=1
        original=x.copy()
        transformed=project_queries(x)
        gate=Gate({'horizon_steps':20,'relative_margin':.01})
        packet=dict(seq=1,observed_ns=1_000_000_000,residual=-.04)
        obs=runtime_features(np.zeros(6),np.zeros(4),20.,tuple(float(v) for v in G['paths']['dlc220']),
            gate,packet,False,0,0.,1_020_000_000)
        np.testing.assert_allclose(transformed[0,9:],obs[9:],atol=1e-7)
        np.testing.assert_array_equal(x,original)

    def test_oracle_channels_cannot_enter_predict(self):
        model=CausalStudent(np.zeros(20),np.ones(20))
        for channel in REMOVED:
            obs=np.zeros(20,np.float32);obs[channel]=1
            with self.assertRaises(ValueError):model.predict(obs)

    def test_deadline_overrun_revokes_fresh_learned_action(self):
        gate=Gate({'horizon_steps':20,'relative_margin':.01});gate.weight=.4
        packet=dict(observed_ns=100)
        result=final_command(gate,(.1,.4,'earned',1.,.8),packet,1000,.02,999)
        self.assertEqual(result[:3],(.02,0.,'deadline'))
        self.assertEqual(gate.weight,0.)

if __name__=='__main__':unittest.main()
