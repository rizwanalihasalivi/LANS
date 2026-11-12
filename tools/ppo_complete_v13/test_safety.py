"""Opened regression and independent model checks for the shared guardian."""
import json,math
from pathlib import Path
import numpy as np
import pytest
from integrations.unified_lans.physics import Command,advance,constrain,errors
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.traffic import velocity
from tools.unified_control_v4.control import ScheduledLQR
from tools.unified_control_v8.control import Controller as Old
from tools.unified_control_v9.learning import setup as make_controller
from tools.ppo_benefit_v10.core import PARAMS
from .safety import Controller

ROOT=Path(__file__).resolve().parents[2]


def case53():
    return json.loads((ROOT/'results/ppo-explore-v12/evaluation/053-adaptive-0.json').read_text())['case']


def python_profile(c,z,previous,first,burst_s,model,vehicles,horizon):
    state=z.copy();last=previous;cost=0.;heading=0.;rate_energy=0.;margin=1e9;maximum_speed=state[3]
    baseline=ScheduledLQR(c.baseline_fn.penalty);baseline.stiffness=c.feedback_stiffness
    for i in range(math.ceil(horizon/c.cfg.dt)):
        acc=c.cfg.max_accel if i*c.cfg.dt<burst_s-1e-9 else float(np.clip(.8*(c.target_speed-state[3]),-c.cfg.max_brake,c.cfg.max_accel))
        desired=first if i==0 else baseline(state,c.route)
        command=constrain(Command(desired,acc),last,c.cfg)
        state=advance(state,command,c.cfg.dt,model);maximum_speed=max(maximum_speed,state[3])
        e,_=errors(state,c.route);rate=(command.steering-last.steering)/c.cfg.dt
        if i*c.cfg.dt<c.cfg.horizon-1e-9:
            cost+=c.cfg.dt*(8*e[0]**2+2*e[2]**2+.03*command.steering**2+.02*rate**2)
            heading+=c.cfg.dt*e[2]**2;rate_energy+=c.cfg.dt*rate**2
        margin=min(margin,1.75-abs(e[0]));t=(i+1)*c.cfg.dt
        for _,other,unc in vehicles:
            p=other[:2]+velocity(other)*t
            margin=min(margin,float(np.linalg.norm(p-state[:2]))-2*c.cfg.vehicle_radius-c.cfg.buffer-unc-c.cfg.uncertainty_rate*t)
        last=command
    return [cost,margin,heading,rate_energy,maximum_speed]


def test_clearance_guard_matches_independent_python_models():
    case=case53();c,clock,state,npcs,net=make_controller(case,'deterministic',Controller,PARAMS,grid=True)
    net.emit(0.,state,npcs,c.inbox);previous=c.issued;row=c.decide(0.)
    assert row['risk']=='DANGER' and row['safety_active'] and row['source']=='safety_clear'
    z=c.forecast(0.);old=c.supervisor.state;risk=c.supervisor.assess(z,c.inbox,c.expected,0.,c.delay);c.supervisor.state=old
    width=c.stiffness_uncertainty;center=c.stiffness_estimate
    models=[max(.7,center-width),center,min(1.3,center+width)]
    expected=np.asarray([python_profile(c,z,previous,row['issued_steering'],row['safety_burst_remaining_s'],m,risk.vehicles,row['safety_horizon_s']) for m in models])
    actual=c._safety_scores(z,previous,row['issued_steering'],c.cfg.max_accel,row['safety_burst_remaining_s'],risk.vehicles,row['safety_horizon_s'])
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-11)
    assert expected[:,1].min()>0 and row['eligible']['safety_clear']


@pytest.mark.parametrize('mode',['lqr','deterministic'])
def test_opened_crossing_is_repaired_with_same_fifo_and_limits(mode):
    case=case53();params=dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr')
    c,clock,state,npcs,net=make_controller(case,mode,Controller,params,grid=mode!='lqr')
    applied=[];last=Command();min_clear=math.inf;maximum=state[3]
    for i in range(120):
        now=i*.05;clock.now=now;net.emit(now,state,npcs,c.inbox);row=c.decide(now)
        assert c.pending[-1]==(now+case['delay'],c.issued)
        assert abs(c.issued.steering-last.steering)<=.03+1e-12
        assert abs(c.issued.steering)<=.5 and -6<=c.issued.accel<=2.5
        if row['safety_strategy']=='clear_conflict':assert row['safety_margin']>=0
        if i==0:assert row['risk']=='DANGER' and row['source']=='safety_clear'
        state=c.apply(now,state,case['stiffness']);move_npcs(npcs,.05,c.route,case['scenario'])
        truth=truth_metrics(state,npcs,c.route,c.cfg)
        assert not truth['collision'] and not truth['corridor_exceeded']
        applied.append(c.applied.accel);min_clear=min(min_clear,truth['true_clearance']);maximum=max(maximum,state[3]);last=c.issued
    assert applied[:2]==[0.,0.] and applied[2]==2.5
    assert min_clear>1.5 and maximum<=17.3 and state[0]>95
    assert abs(state[3]-case['speed'])<.05


def test_missing_traffic_preserves_braking_and_original_pending_fifo():
    case=case53();c,clock,state,npcs,net=make_controller(case,'deterministic',Controller,PARAMS,grid=True)
    net.emit(0.,state,npcs,c.inbox);first=c.decide(0.);assert first['safety_active']
    initial_pending=c.pending.copy();state=c.apply(0.,state,case['stiffness']);clock.now=.05
    net.emit(.05,state,npcs,c.inbox);c.inbox.latest.pop('cross')
    row=c.decide(.05)
    assert row['safety_strategy']=='stale_brake' and row['risk']=='DANGER' and c.issued.accel==-6
    assert c.pending[:-1]==initial_pending and c.pending[-1][0]==pytest.approx(.15)


def test_safe_nonconflicting_traffic_remains_identical_to_old_owner():
    case=dict(case53(),scenario='following',speed=8.,delay=.05,lateral=.2,heading=0.,npc_x_shift=20.)
    a,clock_a,za,na,net_a=make_controller(case,'lqr',Controller,dict(PARAMS,adaptive=False,mpc=False),grid=False)
    b,clock_b,zb,nb,net_b=make_controller(case,'lqr',Old,dict(PARAMS,adaptive=False,mpc=False),grid=False)
    for i in range(24):
        now=i*.05;clock_a.now=clock_b.now=now;net_a.emit(now,za,na,a.inbox);net_b.emit(now,zb,nb,b.inbox)
        ra=a.decide(now);rb=b.decide(now);assert not ra['safety_active']
        assert a.issued==b.issued and ra['risk']==rb['risk']
        za=a.apply(now,za,case['stiffness']);zb=b.apply(now,zb,case['stiffness'])
        move_npcs(na,.05,a.route,case['scenario']);move_npcs(nb,.05,b.route,case['scenario'])
        np.testing.assert_array_equal(za,zb)
