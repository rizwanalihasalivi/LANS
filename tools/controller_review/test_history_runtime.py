import json
from pathlib import Path
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/reviewer_v5'))
from history5 import HistoryEnv
from laptop_full_controller import controller,observation,episode,np


class Runtime(unittest.TestCase):
    def test_legacy_and_history_model_mix_rejected_before_execution(self):
        for model,profile in (('causal_query_v2','fresh_history'),('causal_filter_history_v5','fresh_v4')):
            with tempfile.TemporaryDirectory() as path:
                p=Path(path);(p/'manifest.json').write_text(json.dumps(dict(profile=model)))
                with self.assertRaises(ValueError):episode(None,'nominal',701,profile,1.,p,p)
    def test_runtime_history_equals_training_feature(self):
        e=HistoryEnv(case=(20,'dlc220',1,'nominal',1416000999));e.reset()
        c=controller('fresh_history');c.previews=e.ctrl.previews.copy()
        for f in (-.08,-.04,0.,.04,.08):
            e.ctrl.filtered=f;e._history();c.filtered=f
            x=observation(e.state,e.estimate,e.measured_speed,c.previews,c,0.)
            if c.policy_history_feature:x[14]=float(np.clip(c.filtered/.08,-1.,1.))
            np.testing.assert_array_equal(e.obs,x)
        self.assertFalse(controller('fresh_v4').policy_history_feature)


if __name__=='__main__':unittest.main()
