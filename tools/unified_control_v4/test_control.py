import numpy as np
import pytest
from integrations.unified_lans.physics import Command,Route,Config,advance,baseline
from integrations.unified_lans.traffic import Packet
from integrations.unified_lans.controller import Proposal
from tools.unified_campaign.study import Clock
from tools.unified_control_v4.control import Controller,ScheduledLQR
from tools.unified_control_v4.kernels import step,rollout,lqr


def test_unmodified_gain_matches_original_at_exact_scheduled_speed():
    z=np.array([0.,.2,.01,12.,.02,.01]);route=Route('sine')
    assert ScheduledLQR(1.)(z,route)==pytest.approx(baseline(z,route),abs=1e-12)


def test_prediction_rejects_corridor_violation_even_without_traffic():
    pipe=Controller(Route(),penalty=16.,clock=Clock())
    z=np.array([0.,2.,0.,12.,0.,0.])
    value,margin=pipe.cost(z,Command(),0.,0.,(),.5)
    assert np.isfinite(value) and margin<0


def test_model_identification_uses_measurements_and_actual_commands():
    pipe=Controller(Route(),penalty=16.,adaptive=True,clock=Clock())
    z=np.array([0.,.1,0.,12.,0.,0.]);true_stiffness=.8
    for i in range(30):
        now=i*.05;pipe.inbox.ingest(Packet('ego',i,now,tuple(z)),now);pipe.update_model()
        # An externally specified applied command excites the identifiable dynamics.
        u=Command(.02*np.sin(i*.2),0.);pipe.pending.append((now,u));z=pipe.apply(now,z,true_stiffness)
    assert abs(pipe.stiffness_estimate-true_stiffness)<.05


def test_discrete_identifier_recovers_unlisted_parameter_without_truth_input():
    pipe=Controller(Route(),penalty=16.,adaptive=True,clock=Clock())
    z=np.array([0.,.1,0.,12.,0.,0.])
    for i in range(35):
        now=i*.05;pipe.inbox.ingest(Packet('ego',i,now,tuple(z)),now);pipe.update_model()
        u=Command(.02*np.sin(i*.3),0.);pipe.pending.append((now,u));z=pipe.apply(now,z,.83)
    assert abs(pipe.stiffness_estimate-.83)<.01
    assert pipe.stiffness_uncertainty>=.025


def test_ego_blackout_keeps_source_age_and_disables_ppo_while_braking():
    clock=Clock();pipe=Controller(Route('sine'),penalty=16.,adaptive=True,clock=clock)
    z=np.array([0.,.2,0.,12.,0.,0.])
    for i in range(55):
        now=i*.05;clock.now=now
        if i<4:pipe.inbox.ingest(Packet('ego',i,now,tuple(z)),now)
        decision=pipe.decide(now);z=pipe.apply(now,z,.8)
        if now>.4:
            assert decision['source'] in ('backup_lqr','hold_brake')
            assert decision['issued_accel']==-6. and pipe.features(now) is None
            assert decision['ego_age']==pytest.approx(now-.15)
    assert z[3]==0.


def test_no_history_is_not_fabricated_into_a_measurement():
    clock=Clock(.5);pipe=Controller(Route(),clock=clock)
    z=(0.,0.,0.,12.,0.,0.)
    pipe.inbox.ingest(Packet('ego',0,0.,z),0.)
    assert pipe.reconstruct(.5) is None
    d=pipe.decide(.5);assert d['source']=='hold_brake' and d['issued_accel']==-6.


def test_candidate_comparison_does_not_invent_uncommitted_future_residuals():
    pipe=Controller(Route(),penalty=16.,clock=Clock())
    z=np.array([0.,.2,0.,12.,0.,0.]);first=Command(-.02,0.)
    short=pipe.cost(z.copy(),first,-.02,0.,(),.05)
    long=pipe.cost(z.copy(),first,-.02,0.,(),.5)
    np.testing.assert_array_equal(short,long)


def test_compiled_prediction_matches_python_plant_and_baseline():
    from tools.unified_campaign.study import StudyRoute
    for stiffness in [.7,1.,1.3]:
        for speed in [1.,8.,16.]:
            route=StudyRoute('sine',-1,7.,1.15)
            pipe=Controller(route,penalty=16.,clock=Clock())
            z=np.array([10.,.2,.01,speed,.03,.02]);u=Command(.02,-.5)
            np.testing.assert_allclose(step(z,u.steering,u.accel,.05,stiffness),advance(z,u,.05,stiffness),atol=1e-12,rtol=0)
            assert lqr(z,pipe._gains,*pipe._route)==pytest.approx(pipe.baseline_fn(z,route),abs=1e-12)


def test_compiled_cost_matches_independent_python_rollout():
    pipe=Controller(Route('sine'),penalty=16.,clock=Clock());z=np.array([0.,.2,.01,12.,.02,.01])
    first=-.02;previous=0.;cost=0.;heading=0.;rate=0.;state=z.copy()
    from integrations.unified_lans.physics import constrain,errors
    for i in range(10):
        steer=first if i==0 else constrain(Command(pipe.baseline_fn(state,pipe.route),0.),Command(previous,0.),pipe.cfg).steering
        state=advance(state,Command(steer,0.),.05,.8);e,_=errors(state,pipe.route);r=(steer-previous)/.05
        cost+=.05*(8*e[0]**2+2*e[2]**2+.03*steer**2+.02*r*r);heading+=.05*e[2]**2;rate+=.05*r*r;previous=steer
    result=rollout(z,first,0.,0.,.05,.5,.8,pipe._gains,pipe._route,np.empty((0,7)),2.3,.5,.6,.5,.6)
    np.testing.assert_allclose([result[0],result[2],result[3]],[cost,heading,rate],atol=1e-12,rtol=0)


def test_predictive_plan_has_bounded_rate_and_residual_and_equilibrium():
    from tools.unified_control_v4.mpc import Planner,matrices
    from dataclasses import replace
    cfg=replace(Config(),horizon=1.);planner=Planner();route=Route()
    z=np.array([0.,0.,0.,12.,0.,0.])
    plan=planner.plan(z,route,0.,cfg,1.,16.)
    assert plan is not None and np.max(np.abs(plan))<1e-8
    z[1]=.3;plan=planner.plan(z,route,0.,cfg,1.,16.)
    assert plan is not None and np.max(np.abs(np.diff(np.r_[0.,plan])))<=.03+1e-5
    assert np.max(abs(plan))<=.5+1e-5 and plan[0]<0.
