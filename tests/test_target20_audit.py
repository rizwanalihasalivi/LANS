"""The new target must not be passed through aggregation or float boundary bugs."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/controller_review'))
from check_target20 import evaluate

def matrix(value):
    rows=[]
    for pair in range(3):
        for scene in ('nominal','tire'):
            for source in ('lqr','student_rk','planner_rk','ppo_euler','ppo_rk'):
                rows.append(dict(pair=str(pair),speed='15',path='dlc220',mirror='1',scenario=scene,noise_id=str(pair),source=source,rmse_m=str(value if source=='ppo_rk' else 1.),heading_rmse_rad='1',rate_rms_rad_s='1',survived='True'))
    return rows
class TargetContracts(unittest.TestCase):
    def test_exact_boundary(self):self.assertTrue(evaluate(matrix(.8))['matched_diagnostic_pass'])
    def test_less_than_required_gain(self):self.assertFalse(evaluate(matrix(.81))['matched_diagnostic_pass'])
    def test_nominal_regression_cannot_hide_in_aggregate(self):
        rows=matrix(.1)
        for r in rows:
            if r['source']=='ppo_rk' and r['scenario']=='nominal':r['rmse_m']='1.03'
        self.assertIn('nominal_more_than_2pct_worse_lqr',evaluate(rows)['reasons'])
    def test_failure_cannot_hide(self):
        rows=matrix(.79);rows[-1]['survived']='False';self.assertFalse(evaluate(rows)['matched_diagnostic_pass'])
    def test_unmatched_grid_rejected(self):
        with self.assertRaises(AssertionError):evaluate(matrix(.79)[:-1])
class RuntimeIdentityContracts(unittest.TestCase):
    def methods(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/reviewer_v10'))
        from runtime10 import validate_response as new
        from runtime9 import validate_response as old
        return old,new
    def packet(self):return dict(seq=1,observed_ns=10,entered_ns=20,inferred_ns=30,sent_ns=40,residual=.04)
    def test_boolean_id_was_equal_to_integer_request(self):
        old,new=self.methods();m=self.packet();m['seq']=True;old(m,(1,10),50)
        with self.assertRaises(RuntimeError):new(m,(1,10),50)
    def test_boolean_observation_timestamp_rejected(self):
        old,new=self.methods();m=self.packet();m['observed_ns']=True;old(m,(1,1),50)
        with self.assertRaises(RuntimeError):new(m,(1,1),50)
    def test_valid_response_preserved(self):
        old,new=self.methods();m=self.packet();old(m,(1,10),50);new(m,(1,10),50)
if __name__=='__main__':unittest.main()
