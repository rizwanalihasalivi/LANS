import math
from tools.unified_control_v7.phases import rmse


def test_early_termination_cannot_disappear_from_later_phase_metrics():
    rows=[dict(error=0.) for _ in range(20)]
    assert rmse(rows,0.,1.)==0.
    assert rmse(rows,1.,6.)==2.5
    assert abs(rmse(rows,0.,6.)-math.sqrt(100*2.5**2/120))<1e-12


def test_phase_squared_errors_reconcile_to_the_unchanged_whole_metric():
    rows=[dict(error=.3 if i<20 else .01) for i in range(120)]
    initial=rmse(rows,0.,1.);later=rmse(rows,1.,6.);whole=rmse(rows,0.,6.)
    assert abs(whole**2-(20*initial**2+100*later**2)/120)<1e-12
