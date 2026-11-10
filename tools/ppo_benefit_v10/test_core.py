import json
import numpy as np
import pytest
from integrations.unified_lans.physics import Command
from tools.unified_campaign.study import make_case
from .core import Env,observation,predicted_application,teacher


def fixture(delay=0.):
    case=make_case('training',0);case.update(stage='unit_test_only',delay=delay)
    env=Env();env.reset(seed=42,options=dict(case=case));return env


def test_new_action_cannot_change_already_issued_transition():
    a=fixture();b=fixture()
    try:
        _,_,_,_,ra=a.step([1.]);_,_,_,_,rb=b.step([-1.])
        np.testing.assert_array_equal(ra['state_after'],rb['state_after'])
        assert ra['decision']['proposal_age'] is None
        assert a.decision['proposal_age']==pytest.approx(.05)
    finally:a.close();b.close()


def test_teacher_does_not_change_control_history_queue_plan_or_supervisor():
    env=fixture()
    try:
        c=env.pipe;before=(c._plan,c._plan_residual,c._cost_reference,c.supervisor.state,list(c.pending),list(c.history),c.issued)
        action,info=teacher(c,0.)
        after=(c._plan,c._plan_residual,c._cost_reference,c.supervisor.state,list(c.pending),list(c.history),c.issued)
        for x,y in zip(before,after):assert x is y or x==y
        assert -1<=action<=1 and info['reason'] in ('searched','danger')
        assert env.obs.shape==(30,) and np.isfinite(env.obs).all()
    finally:env.close()


def test_expiry_boundary_still_excludes_teacher_and_ppo():
    env=fixture(.1)
    try:
        assert teacher(env.pipe,0.)[1]['reason']=='strict_expiry'
        env.step([.3]);assert 'ppo' not in env.decision['eligible']
        assert env.decision['proposal_age']==pytest.approx(.15)
    finally:env.close()


def test_future_prediction_uses_known_queue_and_model_not_true_stiffness():
    env=fixture(.05)
    try:
        c=env.pipe;now=0.;state=c.reconstruct(now)
        # One known issued command starts after 50 ms and is then held.
        expected=c.predict(state,c.applied,.05);expected=c.predict(expected,c.issued,.05)
        np.testing.assert_allclose(predicted_application(c,now),expected,rtol=0,atol=1e-12)
        obs,_=observation(c,0.,.2);env.case['stiffness']=.71
        np.testing.assert_array_equal(observation(c,0.,.2)[0],obs)
    finally:env.close()
