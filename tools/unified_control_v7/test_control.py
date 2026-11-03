import numpy as np
from integrations.unified_lans.physics import Config,Command
from integrations.unified_lans.traffic import Packet
from tools.unified_campaign.study import StudyRoute,Clock
from tools.unified_control_v5.control import baseline_plan
from tools.unified_control_v7.control import Controller,trace,linearized_prediction


def instance():
    route=StudyRoute('sine',1,14.,1.2);y,h,_=route.geometry(0.)
    state=np.array([0.,y+.25,h+.01,12.,0.,0.]);clock=Clock()
    c=Controller(route,cfg=Config(horizon=1.),clock=clock,penalty=16.,mpc=True,quality_factor=1.10)
    return c,state,clock


def test_causal_conic_model_reproduces_its_nonlinear_reference():
    c,state,_=instance();n=20
    commands=baseline_plan(state,n,-2.,0.,.05,1.,c._gains,c._route,.5,.6,1.)
    states=trace(state,commands,-2.,.05,1.)
    ef,em,hf,hm,*_=linearized_prediction(state,states,commands,-2.,1.,c._gains,c._route,1.)
    expected_error=np.array([z[1]-c.route.geometry(z[0])[0] for z in states])
    expected_heading=np.array([z[2]-c.route.geometry(z[0])[1] for z in states])
    np.testing.assert_allclose(ef+em@commands,expected_error,rtol=0,atol=1e-8)
    np.testing.assert_allclose(hf+hm@commands,expected_heading,rtol=0,atol=1e-8)


def test_conic_proposal_has_actuator_limits_and_stale_ego_never_calls_it():
    c,state,clock=instance();plan=c.planner.plan(state,c.route,0.,c.cfg,1.,16.)
    assert c.planner.status=='Solved' and plan is not None
    assert np.max(abs(plan))<=.5 and np.max(abs(np.diff(np.r_[0.,plan])))<=.03+1e-12
    c.inbox.ingest(Packet('ego',1,0.,tuple(state)),0.);clock.now=.3
    before=c.planner.calls;decision=c.decide(.3)
    assert c.planner.calls==before and decision['ego_backup']
    assert decision['issued_accel']==-6. and decision['source']=='hold_brake'


def test_estimator_and_full_controller_receive_only_observed_applied_history():
    c,state,clock=instance();c.adaptive=True
    for i in range(12):
        now=i*.05;clock.now=now;c.inbox.ingest(Packet('ego',i,now,tuple(state)),now)
        decision=c.decide(now);previous=c.applied;state=c.apply(now,state,.83)
        assert abs(c.applied.steering-previous.steering)<=.03+1e-12
        assert -6<=c.applied.accel<=2.5 and decision['complete_decision_ms']>=0.
    assert abs(c.stiffness_estimate-.83)<.01
