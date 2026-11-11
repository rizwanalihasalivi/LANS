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
