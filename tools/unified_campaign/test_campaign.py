import copy
import numpy as np
import pytest
from integrations.unified_lans.controller import Pipeline, Proposal
from integrations.unified_lans.physics import Route
from tools.unified_campaign.study import Env, Clock, make_case, setup as setup_case
from tools.unified_campaign.campaign import PROTOCOL, assess


def test_logical_time_training_is_independent_of_wall_clock(monkeypatch):
    a=Env();b=Env();x,_=a.reset(seed=123);y,_=b.reset(seed=123)
    np.testing.assert_array_equal(x,y)
    for i in range(12):
        monkeypatch.setattr('time.monotonic',lambda:1000.+i)
        x,ra,da,ta,_=a.step([.3])
        monkeypatch.setattr('time.monotonic',lambda:9000.+i)
        y,rb,db,tb,_=b.step([.3])
        np.testing.assert_array_equal(x,y);assert (ra,da,ta)==(rb,db,tb)


def test_protocol_separates_training_development_and_reserved_definitions():
    a=make_case('development',0);b=make_case('reserved',0)
    assert a['network_seed']!=b['network_seed'] and a['phase']!=b['phase']
    assert a['lateral']!=b['lateral']


def results(gain=.1):
    rows=[]
    for i in range(32):
        case=make_case('development',i)
        for mode in ['lqr','fixed','deterministic','optimized']:
            rows.append(dict(case=case,mode=mode,actor=0,rmse_m=1.,heading_rms=.1,rate_rms=.1,
                             progress_m=50.,failed=False))
        for actor in PROTOCOL['seeds']:
            rows.append(dict(case=case,mode='hybrid',actor=actor,rmse_m=1-gain,heading_rms=.1,rate_rms=.1,
                             progress_m=50.,failed=False))
    return rows


def test_gate_accepts_only_meaningful_balanced_improvement():
    assert assess(results())['passed']
    assert not assess(results(.001))['passed']


def test_gate_does_not_reward_stopping_or_select_a_favorable_actor():
    rows=results()
    next(r for r in rows if r['mode']=='hybrid')['progress_m']=1.
    assert not assess(rows)['passed']
    rows=results()
    for r in rows:
        if r['actor']==43:r['rmse_m']=1.01
    assert not assess(rows)['passed']


def test_clock_default_and_grid_limits_remain_explicit():
    with pytest.raises(ValueError):Pipeline(Route(),deterministic_grid=[.09])
    with pytest.raises(ValueError):Pipeline(Route(),target_speed=0.)
    pipe,clock,ego,npcs,net=setup_case(make_case('development',0))
    net.emit(0.,ego,npcs,pipe.inbox)
    assert pipe.accept(Proposal(1,0.,0.,.01,0.),0.)
    assert pipe.features(0.).shape==(17,)
