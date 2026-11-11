from dataclasses import replace
import numpy as np
import pytest
from integrations.unified_lans.physics import Command,constrain,advance
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v9.learning import setup as build_pipeline
from tools.unified_control_v8.control import Controller as Base
from tools.ppo_benefit_v10.core import PARAMS
from .control import Controller,PlanProposal,commands
from .probe import teacher


def owner(delay=0.,cls=Controller):
    case=dict(cases()[0],delay=delay)
    return case,build_pipeline(case,'deterministic',cls,PARAMS,grid=True)


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_no_proposal_exactly_preserves_strong_analytical_trajectory(delay):
    case,(a,clock,ego,npcs,net)=owner(delay);_,(b,bclock,bego,bnpcs,bnet)=owner(delay,Base)
    from integrations.unified_lans.simulation import move_npcs
    for i in range(6):
        now=i*.05;clock.now=now;bclock.now=now
        net.emit(now,ego,npcs,a.inbox);bnet.emit(now,bego,bnpcs,b.inbox)
        x=a.decide(now);y=b.decide(now)
        assert x['issued_steering']==y['issued_steering'] and x['issued_accel']==y['issued_accel']
        ego=a.apply(now,ego,case['stiffness']);bego=b.apply(now,bego,case['stiffness'])
        move_npcs(npcs,.05,a.route,case['scenario']);move_npcs(bnpcs,.05,b.route,case['scenario'])
        np.testing.assert_allclose(ego,bego,rtol=0,atol=1e-12)


def test_invalid_expired_and_reordered_plans_are_rejected():
    _,(c,clock,*_)=owner(.1);clock.now=.05
    p=PlanProposal(1,0.,0.,0.,tuple(np.zeros(8)))
    assert c.accept_plan(p,.05) and not c.fresh_plan(.05)
    assert not c.accept_plan(p,.05)
    for bad in [replace(p,sequence=2,knots=()),replace(p,sequence=2,knots=((1,2),)*8),
        replace(p,sequence=2,knots=(float('nan'),)*8),replace(p,sequence=2,knots=(1.1,)*8),
        replace(p,sequence=2,observed_s=.2),replace(p,sequence=2,wall_observed=.2)]:
        assert not c.accept_plan(bad,.05)


def test_first_response_has_zero_shift_and_cannot_execute_before_service_time():
    case,(c,clock,ego,npcs,net)=owner();net.emit(0.,ego,npcs,c.inbox)
    p=PlanProposal(1,0.,0.,0.,tuple(np.zeros(8)))
    assert c.accept_plan(p,0.)
    assert not c.decide(0.)['sequence_plan_selected']
    ego=c.apply(0.,ego,case['stiffness']);clock.now=.05;net.emit(.05,ego,npcs,c.inbox)
    r=c.decide(.05);assert r['sequence_shift']==0


def test_projection_matches_independent_python_bounds_and_physics():
    _,(c,_,state,*_)=owner();knots=np.linspace(-1,1,8)
    plan=commands(state,knots,0,0.,0.,.05,40,1.,c._gains,c._route,1.)
    z=state.copy();previous=Command()
    for i,u in enumerate(plan):
        residual=.08*np.interp(i*7/39,np.arange(8),knots)
        expected=constrain(Command(c.baseline_fn(z,c.route)+residual,0.),previous,c.cfg)
        assert u==pytest.approx(expected.steering,abs=1e-12)
        z=advance(z,Command(float(u),0.),.05,1.);previous=Command(float(u),0.)


def test_teacher_is_causal_and_does_not_mutate_owner_decision_state():
    _,(c,clock,ego,npcs,net)=owner();net.emit(0.,ego,npcs,c.inbox);c.decide(0.)
    old=(c.issued,list(c.pending),c._plan,c._cost_reference,c.supervisor.state)
    action,info=teacher(c,0.)
    assert len(action)==8 and np.isfinite(action).all() and max(abs(x) for x in action)<=1
    assert c.issued==old[0] and c.pending==old[1] and c._plan is old[2] and c._cost_reference is old[3] and c.supervisor.state==old[4]
