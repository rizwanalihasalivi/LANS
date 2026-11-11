import json
import numpy as np
from . import evaluate
from .train import curriculum


def test_corrected_v11_is_a_required_independent_comparator():
    records=[]
    for i in range(2):
        for mode in evaluate.MODES:
            for seed in ((0,) if mode in ('lqr','adaptive') else evaluate.SEEDS):
                records.append(dict(case=dict(id=i,scenario='following',speed=8.,delay=0.),mode=mode,seed=seed,
                    rmse_m=.88 if mode=='ppo' else 1.,heading_rms=.01,rate_rms=.02,progress_m=60.,failed=False,selected_ticks=1))
    assert evaluate.assess(records)['requested_10_passed']
    for r in records:
        if r['mode']=='v11':r['rmse_m']=.8
    result=evaluate.assess(records)
    assert not result['requested_10_passed'] and 'confidence_v11' in result['reasons']


def test_old_and_new_sequence_models_do_not_share_predictions(tmp_path,monkeypatch):
    class Constant:
        def __init__(self,value):self.value=value
        def predict(self,query,deterministic=True):return np.full(8,self.value),None
    monkeypatch.setattr(evaluate,'OUT',tmp_path);(tmp_path/'protocol.json').write_text('{}')
    monkeypatch.setattr(evaluate,'MODELS',{'v11-42':Constant(.1),'ppo-42':Constant(-.1)})
    original=evaluate.frozen.run
    monkeypatch.setattr(evaluate.frozen,'run',lambda case,mode,seed:original(case,mode,seed,steps=6))
    case=dict(curriculum(np.random.default_rng(42)),id=0)
    a=evaluate.worker((case,'v11',42));b=evaluate.worker((case,'ppo',42))
    assert a['mode']=='v11' and b['mode']=='ppo'
    old=json.loads((tmp_path/'000-v11-42.jsonl').read_text().splitlines()[0])
    new=json.loads((tmp_path/'000-ppo-42.jsonl').read_text().splitlines()[0])
    np.testing.assert_allclose(old['label'],.1);np.testing.assert_allclose(new['label'],-.1)
