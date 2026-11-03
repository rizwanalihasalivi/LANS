import json
import math
from pathlib import Path
import time
import numpy as np
import pytest
from integrations.unified_lans.physics import Config, Command, Route, advance, constrain, baseline
from integrations.unified_lans.traffic import Packet, Inbox, Supervisor, contact_time, conflict_time
from integrations.unified_lans.controller import Pipeline, Proposal
from integrations.unified_lans.learning import TrainingEnv
from integrations.unified_lans.inference import load_policy
from integrations.unified_lans.simulation import Network, initial, move_npcs


Z=np.array([0.,.2,0.,12.,0.,0.])


def ready(delay=0.):
    pipe=Pipeline(Route(),delay=delay)
    pipe.inbox.ingest(Packet('ego',0,0.,tuple(Z)),0.)
    return pipe


def test_reference_geometry_does_not_move_unsteered_vehicle():
    a=advance(Z,Command(),.5)
    np.testing.assert_allclose(a[[1,2,4,5]],Z[[1,2,4,5]])
    assert a[0]==pytest.approx(6.)


def test_rk4_is_consistent_with_fine_integration():
    a=advance(Z,Command(.03,-1.),.2)
    b=Z.copy()
    for _ in range(200):b=advance(b,Command(.03,-1.),.001)
    np.testing.assert_allclose(a,b,atol=2e-6,rtol=0)


def test_stopped_vehicle_stays_finite_under_braking():
    a=Z.copy();a[3]=0.
    a=advance(a,Command(.1,-6.),1.)
    assert np.isfinite(a).all() and a[3]==0.


def test_limits_do_not_double_fuse_or_allow_nan():
    c=constrain(Command(1.,-20.),Command(),Config())
    assert c.steering==pytest.approx(.03) and c.accel==-6.
    with pytest.raises(ValueError):constrain(Command(math.nan,0.),Command(),Config())


@pytest.mark.parametrize('seq,stamp,state',[(True,0.,tuple(Z)),(0,.1,tuple(Z)),(0,0.,(0.,)*5),
                                         (0,0.,(math.nan,)*6),(-1,0.,tuple(Z))])
def test_packet_rejects_malformed_identity_future_and_nonfinite(seq,stamp,state):
    inbox=Inbox()
    assert not inbox.ingest(Packet('ego',seq,stamp,state),0.)
    assert not inbox.latest


def test_out_of_order_delivery_never_refreshes_original_age():
    inbox=Inbox()
    assert inbox.ingest(Packet('lead',2,.1,tuple(Z)),.2)
    assert not inbox.ingest(Packet('lead',1,0.,tuple(Z)),.2)
    assert inbox.latest['lead'].observed_s==.1


def test_applied_history_reconstructs_measurement_without_using_truth():
    pipe=ready();command=Command(.01,.5);pipe.pending=[(0.,command)]
    truth=pipe.apply(0.,Z)
    np.testing.assert_allclose(pipe.reconstruct(.05),truth,atol=1e-12)


def test_command_fifo_forecast_uses_actual_pending_order():
    pipe=ready(.1);pipe.pending=[(.05,Command(.02,-2.))]
    expected=advance(advance(Z,Command(),.05),Command(.02,-2.),.05)
    np.testing.assert_allclose(pipe.forecast(0.),expected,atol=1e-12)


def test_delayed_command_is_not_applied_early():
    pipe=ready(.1);decision=pipe.decide(0.)
    pipe.apply(0.,Z)
    assert pipe.applied==Command() and len(pipe.pending)==1
    pipe.apply(.05,Z)
    assert pipe.applied==Command()
    pipe.apply(.1,Z)
    assert pipe.applied.steering==decision['issued_steering']


def test_ttc_matches_independent_one_dimensional_contact():
    other=np.array([20.,.2,0.,7.,0.,0.])
    assert contact_time(Z,other,5.)==pytest.approx(3.)
    other[3]=15.
    assert math.isinf(contact_time(Z,other,5.))


def test_crossing_occupancy_detects_conflict_not_unrelated_arrivals():
    ego=np.array([0.,0.,0.,10.,0.,0.]);other=np.array([20.,-20.,math.pi/2,10.,0.,0.])
    assert conflict_time(ego,other,5.)==pytest.approx(1.5)
    other[1]=-100.
    assert math.isinf(conflict_time(ego,other,5.))


def test_missing_neighbor_brakes_and_rejects_residuals():
    pipe=ready();pipe.expected={'missing'}
    assert pipe.accept(Proposal(1,0.,0.,.08,time.monotonic()),0.)
    result=pipe.decide(0.)
    assert result['risk']=='DANGER' and result['issued_accel']==-6.
    assert result['source']=='lqr' and result['residual']==0.
    assert result['missing']==['missing']


def test_traffic_age_inflates_uncertainty_then_expires():
    cfg=Config();supervisor=Supervisor(cfg,'following');inbox=Inbox()
    other=Z.copy();other[0]=30.;other[3]=7.
    inbox.ingest(Packet('lead',1,0.,tuple(other)),0.)
    fresh=supervisor.assess(Z,inbox,{'lead'},0.,0.)
    old=supervisor.assess(Z,inbox,{'lead'},.2,.2)
    assert old.vehicles[0][2]>fresh.vehicles[0][2]
    expired=supervisor.assess(Z,inbox,{'lead'},.45,.45)
    assert expired.state=='DANGER' and expired.missing==('lead',)


def test_stale_ego_uses_hold_brake_without_fabricated_lqr():
    pipe=ready()
    result=pipe.decide(.25)
    assert result['source']=='hold_brake' and result['issued_accel']==-6.


def test_proposal_original_age_includes_application_delay_and_wall_age():
    pipe=ready(.1);wall=time.monotonic()
    assert not pipe.accept(Proposal(1,0.,0.,.02,wall),.1)
    assert not pipe.accept(Proposal(1,0.,0.,.02,wall-1.),0.)
    assert not pipe.accept(Proposal(True,0.,0.,.02,wall),0.)
    assert pipe.accept(Proposal(1,0.,0.,.02,wall),0.)
    assert not pipe.accept(Proposal(1,0.,0.,.02,wall),0.)


def test_expired_proposal_cannot_enter_candidates_at_application_boundary():
    pipe=ready(.1)
    pipe.accept(Proposal(1,0.,0.,.02,time.monotonic()),0.)
    z=pipe.apply(0.,Z)
    pipe.inbox.ingest(Packet('ego',1,.05,tuple(z)),.05)
    result=pipe.decide(.05)
    assert 'ppo' not in result['costs']


def test_dead_worker_enforces_analytical_fallback():
    pipe=ready();pipe.accept(Proposal(1,0.,0.,.08,time.monotonic()),0.)
    result=pipe.decide(0.,worker_failed=True)
    assert result['source']=='lqr' and set(result['costs'])=={'lqr'}


def test_historical_policy_cannot_be_silently_reused():
    path=Path(__file__).resolve().parents[2]/'webots/results/controller-remediation/root-smoke'
    with pytest.raises(ValueError,match='incompatible'):load_policy(path)


def test_zero_residual_gives_exact_constrained_lqr_command():
    pipe=ready();pipe.mode='ppo'
    pipe.accept(Proposal(1,0.,0.,0.,time.monotonic()),0.)
    decision=pipe.decide(0.)
    expected=constrain(Command(baseline(Z,pipe.route),0.),Command(),pipe.cfg)
    assert decision['issued_steering']==expected.steering


def test_training_features_and_reward_follow_real_fusion_and_fifo():
    env=TrainingEnv();obs,_=env.reset(seed=17)
    assert env.observation_space.contains(obs)
    for _ in range(8):
        obs,reward,done,truncated,info=env.step([.5])
        assert env.observation_space.contains(obs) and math.isfinite(reward)
        assert len(env.pipe.history)>0
        if done or truncated:break


def test_network_blackout_does_not_refresh_cached_packet_timestamps():
    network=Network(profile='blackout');inbox=Inbox();route,ego,npcs=initial('following')
    network.emit(.9,ego,npcs,inbox);network.emit(1.1,ego,npcs,inbox)
    assert inbox.latest['lead'].observed_s==.9
    assert inbox.latest['ego'].observed_s==1.1


def test_end_to_end_delayed_multivehicle_loop_keeps_command_constraints():
    route,ego,npcs=initial('crossing');pipe=Pipeline(route,'crossing',delay=.1)
    pipe.expected=set(npcs);network=Network(profile='reordered')
    for i in range(40):
        now=i*pipe.cfg.dt;network.emit(now,ego,npcs,pipe.inbox)
        prior=pipe.applied;decision=pipe.decide(now)
        ego=pipe.apply(now,ego);move_npcs(npcs,pipe.cfg.dt,route,'crossing')
        assert abs(pipe.applied.steering-prior.steering)<=pipe.cfg.steering_rate*pipe.cfg.dt+1e-9
        assert -6<=pipe.applied.accel<=2.5
        assert np.isfinite(ego).all()
