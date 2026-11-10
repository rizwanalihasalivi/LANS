import numpy as np
import pytest
from tools.unified_campaign.study import make_case
from .core import Env
from . import evaluate


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_training_and_prospective_pipeline_have_identical_delayed_commands(delay):
    class Constant:
        def predict(self,obs,deterministic=True):return np.array([.2]),None
    case=make_case('training',0);case.update(delay=delay)
    env=Env();env.reset(seed=42,options=dict(case=case));actual=[]
    try:
        for _ in range(6):
            _,_,_,_,row=env.step([.2]);actual.append(row['state_after'].copy())
    finally:env.close()
    evaluate.MODELS={'ppo-42':Constant()}
    _,rows=evaluate.run(case,'ppo',42,steps=6)
    np.testing.assert_allclose(actual,[r['state_after'] for r in rows],rtol=0,atol=1e-12)


def test_paired_statistics_reject_incomplete_actor_coverage():
    with pytest.raises((AssertionError,KeyError)):evaluate.assess([dict(case=dict(id=0),mode='ppo',seed=42)])


def paired_records():
    rows=[]
    errors={'lqr':1.2,'adaptive':1.,'teacher':.6,'old':.8,'bc':.7,'ppo':.5}
    for i in range(2):
        for mode in evaluate.MODES:
            for seed in (evaluate.SEEDS if mode in ('old','bc','ppo') else [0]):
                rows.append(dict(case=dict(id=i,scenario='following',speed=8.,delay=0.),mode=mode,seed=seed,
                    rmse_m=errors[mode],heading_rms=.01,rate_rms=.02,progress_m=60.,failed=False,ppo_ticks=10))
    return rows


def test_paired_gain_separates_finetuning_from_initialization_and_all_reference_target():
    result=evaluate.assess(paired_records())
    assert result['primary_success'] and result['ppo_finetuning_positive']
    assert result['comparisons']['old']['gain_percent']==pytest.approx(37.5)
    assert result['comparisons']['bc']['gain_percent']==pytest.approx(100*(1-.5/.7))
    assert not result['requested_30']  # Direct teacher is less than 30% behind.


def test_one_actor_failure_blocks_good_average_performance():
    rows=paired_records();next(r for r in rows if r['mode']=='ppo' and r['seed']==44)['failed']=True
    result=evaluate.assess(rows)
    assert not result['primary_success'] and 'actor_44_failure' in result['reasons']
