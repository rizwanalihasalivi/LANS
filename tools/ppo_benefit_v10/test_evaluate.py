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
