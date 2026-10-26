import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import advance as original,GAINS
from comparison import configure_lqr
from gating import Gate,predict_cost
from plant import advance

class Contracts(unittest.TestCase):
    def setUp(self):configure_lqr();self.gate=Gate({'horizon_steps':30,'relative_margin':.02})
    def call(self,packet,baseline=.02,estimate=None):
        return self.gate.choose(.1,baseline,packet,np.zeros(4) if estimate is None else estimate,0.,20.,0.,GAINS[20],'residual')
    def test_nominal_plant_parity(self):
        state=np.array([1.,.2,.03,.1,.02,.01]);np.testing.assert_allclose(advance(state,.04,20.,.9,1.),original(state,.04,20.),rtol=0,atol=1e-14)
    def test_invalid_packet_immediate_fallback(self):
        for packet,reason in [(None,'missing'),((1,.0,.01),'age'),((1,.11,.01),'age'),((1,.1,float('nan')),'nonfinite')]:
            self.gate.weight=.4
            result=self.call(packet);self.assertEqual(result[:3],(.02,0.,reason))
    def test_equal_candidate_never_earns(self):
        for _ in range(10):self.assertEqual(self.call((1,.1,0.))[:3],(.02,0.,'cost'))
    def test_sequence_regression(self):
        self.call((9,.1,.01));self.assertEqual(self.call((8,.1,.01))[2],'sequence')
    def test_accepted_actual_command_improves_prediction(self):
        # Deliberately bad baseline: learned correction toward zero should earn authority.
        for _ in range(4):result=self.call((1,.1,-.02),baseline=.02)
        command,weight,reason,j0,j1=result
        self.assertGreater(weight,0);self.assertLess(command,.02);self.assertLess(j1,j0)
        self.assertAlmostEqual(j1,predict_cost(np.zeros(4),0.,command,20.,0.,GAINS[20],30))
    def test_envelope(self):self.assertEqual(self.call((1,.1,.01),estimate=np.array([2.,0,0,0]))[2],'envelope')
if __name__=='__main__':unittest.main()
