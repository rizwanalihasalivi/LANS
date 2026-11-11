import numpy as np
import pytest
from tools.unified_control_v4.calibrate import cases
from .learning import Env
from . import evaluate


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_sequence_training_and_evaluation_commands_match(delay):
    class Constant:
        def predict(self,obs,deterministic=True):return np.linspace(-.1,.1,8),None
    case=dict(cases()[0],delay=delay);env=Env();env.reset(seed=42,options=dict(case=case));states=[]
    try:
        for _ in range(6):
            _,_,_,_,row=env.step(np.linspace(-.1,.1,8));states.append(row['state_after'].copy())
    finally:env.close()
    evaluate.MODELS={'ppo-42':Constant()};_,rows=evaluate.run(case,'ppo',42,steps=6)
    np.testing.assert_allclose(states,[r['state_after'] for r in rows],rtol=0,atol=1e-12)


def complete_records():
    rows=[]
    for i in range(2):
        for mode in evaluate.MODES:
            for seed in (evaluate.SEEDS if mode in ('scalar','bc','ppo') else [0]):
                rows.append(dict(case=dict(id=i,scenario='following',speed=8.,delay=0.),mode=mode,seed=seed,
                    rmse_m=.88 if mode=='ppo' else 1.,heading_rms=.01,rate_rms=.02,progress_m=60.,failed=False,selected_ticks=1))
    return rows


def test_ten_percent_gate_uses_percentage_and_positive_bc_comparison():
    result=evaluate.assess(complete_records())
    assert result['comparisons']['adaptive']['gain_percent']==pytest.approx(12.)
    assert result['requested_10_passed'] and result['adaptive_ci_lower_at_least_10']


def test_good_mean_cannot_hide_a_single_actor_failure():
    rows=complete_records();next(r for r in rows if r['mode']=='ppo' and r['seed']==43)['failed']=True
    result=evaluate.assess(rows)
    assert not result['requested_10_passed'] and 'actor_43_failure' in result['reasons']
