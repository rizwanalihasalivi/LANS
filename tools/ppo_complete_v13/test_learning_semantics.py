"""Externally specified scorer, terminal, causality and FIFO contracts."""
import math

import numpy as np
import pytest
from stable_baselines3.common.vec_env import DummyVecEnv

from integrations.unified_lans.physics import Config, Route
from integrations.unified_lans.traffic import Packet
from integrations.unified_lans.simulation import move_npcs
from tools.unified_control_v9.learning import setup as make_pipeline
from tools.ppo_benefit_v10.core import PARAMS

from .learning import Env, HORIZON, RunningStats, observe, rmse_reward
from .plans import CorrectionProposal, PlanMixin
from .safety import Controller as SafeController


def fixture(delay=0.):
    return dict(id=0, stage='semantic_test', scenario='following', speed=8.,
        delay=delay, mirror=1, stiffness=1.15, lateral=.25, heading=-.01,
        phase=1.3, amplitude=.9, network='nominal', network_seed=9139,
        npc_x_shift=5., npc_speed_scale=1.)


def reward_for(errors, *, failure_at=None):
    total=0.;squared=0.
    for i,error in enumerate(errors,1):
        failed=i==failure_at
        value,squared=rmse_reward(squared,float(error),i,failed)
        total+=value
        if failed:break
    return total,squared


def test_reward_preserves_score_order_that_old_clipping_reverses():
    # These costs and their ordering specify the target independently of the
    # implementation. Clipping a reference difference reverses that ordering.
    costs_a=np.array([.990,1.004]);costs_b=np.array([.998,.998])
    old_a=np.clip(1000*(1-costs_a),-5,5).sum()
    old_b=np.clip(1000*(1-costs_b),-5,5).sum()
    assert costs_a.sum()<costs_b.sum() and old_a<old_b
    errors_a=np.r_[np.sqrt(costs_a),np.zeros(HORIZON-2)]
    errors_b=np.r_[np.sqrt(costs_b),np.zeros(HORIZON-2)]
    new_a,_=reward_for(errors_a);new_b,_=reward_for(errors_b)
    assert new_a>new_b


def test_reward_telescopes_to_penalized_episode_rmse_and_is_time_order_neutral():
    errors=np.r_[.3,.4,np.zeros(HORIZON-2)]
    reordered=np.r_[.4,.3,np.zeros(HORIZON-2)]
    value,squared=reward_for(errors)
    expected=100*(math.sqrt(1e-12/HORIZON)-math.sqrt((.25+1e-12)/HORIZON))
    assert squared==pytest.approx(.25) and value==pytest.approx(expected,abs=1e-12)
    assert reward_for(reordered)[0]==pytest.approx(value,abs=1e-12)
    failed_value,failed_squared=reward_for([.5,.1,.2],failure_at=3)
    penalized=.5**2+.1**2+.2**2+(HORIZON-3)*6.25
    assert failed_squared==pytest.approx(penalized)
    assert failed_value==pytest.approx(100*(math.sqrt(1e-12/HORIZON)-math.sqrt((penalized+1e-12)/HORIZON)),abs=1e-10)


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_zero_action_is_exact_repaired_reference_for_complete_horizon(delay):
    case=fixture(delay);env=Env();env.reset(seed=3,options={'case':case})
    ref,clock,state,npcs,net=make_pipeline(case,'deterministic',SafeController,dict(PARAMS),grid=True)
    primary=0.;squared=0.
    try:
        for tick in range(HORIZON):
            now=tick*.05;clock.now=now;net.emit(now,state,npcs,ref.inbox)
            expected=ref.decide(now);state=ref.apply(now,state,case['stiffness'])
            move_npcs(npcs,.05,ref.route,case['scenario'])
            observation,reward,terminated,truncated,row=env.step(np.zeros(8))
            assert row['source']==expected['source']
            assert row['issued_steering']==expected['issued_steering']
            assert row['issued_accel']==expected['issued_accel']
            assert not row['sequence_plan_selected']
            np.testing.assert_array_equal(row['state_after'],state)
            primary+=row['reward_parts']['rmse_reward'];squared+=row['error']**2
            assert not truncated and terminated==(tick==HORIZON-1)
        assert observation.shape==(55,) and observation[51]==0.
        assert primary==pytest.approx(100*(math.sqrt(1e-12/HORIZON)-math.sqrt((squared+1e-12)/HORIZON)),abs=1e-9)
        assert row['terminal_reason']=='horizon'
        assert env.pipe._prepared is None
        assert all(due<=(HORIZON-1)*.05+delay+1e-9 for due,_ in env.pipe.pending)
    finally:env.close()


def test_vec_env_exposes_real_terminal_observation_without_timeout_bootstrap():
    vector=DummyVecEnv([lambda:Env(case_sampler=lambda _:fixture(.05))])
    try:
        initial=vector.reset();assert initial[0,51]==1.
        for _ in range(HORIZON):
            _,_,done,info=vector.step(np.zeros((1,8),np.float32))
        assert done.tolist()==[True]
        row=info[0];terminal=row['terminal_observation']
        assert row['terminated'] and not row['truncated']
        assert row['TimeLimit.truncated'] is False
        assert terminal.shape==(55,) and terminal[51]==0. and np.count_nonzero(terminal)>0
        assert terminal[52]==pytest.approx(math.sqrt(row['score_error_sq']/HORIZON)/.25,abs=1e-6)
        assert vector.envs[0].episode==1  # Reset occurred; terminal is not reset obs.
    finally:vector.close()


def test_observation_cannot_read_unreceived_plant_or_shadow_truth():
    env=Env();env.reset(seed=7,options={'case':fixture(.1)})
    try:
        before,valid=observe(env.pipe,env.ctx,env.running,env.last)
        assert valid and env.running.received_samples==0
        env.ego+=np.array([99.,-88.,.9,4.,3.,2.])
        env.sego+=np.array([-100.,100.,-.4,8.,4.,2.])
        for state in env.npcs.values():state[:2]+=200.
        env.case['stiffness']=9.
        env.shadow_heading=100.;env.shadow_rate=10000.
        after,valid=observe(env.pipe,env.ctx,env.running,env.last)
        assert valid
        np.testing.assert_array_equal(before,after)
        assert env.running.received_samples==0
    finally:env.close()


class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now


class CorrectionOwner(PlanMixin,SafeController):pass


def simple_owner(delay):
    clock=Clock();owner=CorrectionOwner(Route('straight'),cfg=Config(horizon=2.),
        delay=delay,clock=clock,mode='lqr',target_speed=8.,penalty=16.,adaptive=False,
        mpc=False,anchor_quality_factor=None)
    state=np.array([0.,.05,.005,8.,0.,0.])
    owner.inbox.ingest(Packet('ego',0,0.,tuple(state)),0.)
    return owner,clock,state


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_admitted_current_action_first_changes_physics_at_actual_fifo_delay(delay):
    actor,clock,state=simple_owner(delay);reference,rclock,rstate=simple_owner(delay)
    context=actor.prepare(0.);rcontext=reference.prepare(0.)
    # A fixed small correction is admissible on this synthetic state under
    # all original robust guards; no mocked selector or future plant read.
    proposal=CorrectionProposal(1,0.,0.,0.,tuple(np.full(8,-.001)))
    selected=actor.finish(context,proposal);baseline=reference.finish(rcontext)
    assert selected['source']=='ppo_anchor' and selected['sequence_plan_selected']
    assert selected['issued_steering']!=baseline['issued_steering']
    assert selected['sequence_age']==pytest.approx(delay)
    assert proposal.observed_s==proposal.submitted_s==proposal.wall_observed==0.
    for tick in range(round(delay/.05)+1):
        now=tick*.05;clock.now=rclock.now=now
        state=actor.apply(now,state,1.);rstate=reference.apply(now,rstate,1.)
        if now<delay-1e-9:
            np.testing.assert_array_equal(state,rstate)
        else:
            assert np.max(np.abs(state-rstate))>1e-9
            assert actor.applied.steering==selected['issued_steering']
