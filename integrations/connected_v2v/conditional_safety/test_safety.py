from fractions import Fraction as F
import json
import math
import pytest
from .shield import Contract,SafetyShield,ContractViolation,envelope,rational
from .audit import flow,gap_minimum,check_episode
from .boundary import run as boundary
from .prove import run as prove


def test_exact_stopping_and_zero_speed():
    assert envelope(F('.1'),F(-5),F(1))==(F('.001'),F(0))
    assert envelope(0,-5,1)==(0,0)
    assert envelope(2,0,F('.05'))==(F('.1'),2)


def test_freshness_and_spatial_memory_are_distinct():
    shield=SafetyShield(0,1)
    assert shield.observe('a','radar',0,0,0,20,F('.2'))
    assert not shield.observe('a','radar',0,0,F('.1'),25,F('.2'))
    assert not shield.observe('a','radar',1,0,1,25,F('.2'))
    assert shield.bounds['a']==20
    # No refresh at t=1: the old lower bound survives, with its old timestamp.
    assert shield.history[('a','radar')]==(0,0)
    assert shield.choose(2)[1]['boundary']=='20'


def test_sources_replay_independently_and_future_rejected():
    shield=SafetyShield(0,1)
    assert shield.observe('a','v2v',10,0,0,20,F('.4'))
    assert shield.observe('a','radar',0,0,0,19,F('.2'))
    assert shield.bounds['a']==20
    assert not shield.observe('a','v2v',11,1,F('.1'),21,F('.4'))


def test_unknown_or_unrecoverable_is_not_certified():
    with pytest.raises(ContractViolation):SafetyShield(0,1).choose(0)
    s=SafetyShield(0,16);s.observe('a','radar',0,0,0,1,F('.2'))
    with pytest.raises(ContractViolation):s.choose(-6)


def test_admission_must_recheck_all_obstacles():
    s=SafetyShield(0,16)
    s.observe('leader','radar',0,0,0,100,F('.2'));s.choose(2)
    s.observe('cutin','radar',0,F('.05'),F('.05'),2,F('.2'))
    with pytest.raises(ContractViolation):s.choose(-6)


def test_refinement_intersects_without_inflation():
    s=SafetyShield(1,2)
    s.refine_ego(10,10);assert (s.x,s.v)==(1,2)
    s.refine_ego(F('.9'),F('1.9'));assert (s.x,s.v)==(F('.9'),F('1.9'))


def test_independent_minimizer_detects_between_samples_collision():
    # Both endpoint gaps are 1 m, but the trajectories overlap inside the tick.
    assert flow(F(1),F(0),F(4),F('1.5'))[0]-flow(F(0),F(6),F(-4),F('1.5'))[0]==1
    assert gap_minimum(F(0),F(6),F(-4),F(1),F(0),F(4),F('1.5'))==F('-1.25')


@pytest.mark.parametrize('value',[True,float('inf'),float('nan'),'nan'])
def test_invalid_numeric_values(value):
    with pytest.raises(ValueError):rational(value)


def test_lans_gain_correspondence():
    from integrations.connected_v2v.formation.controller import following_for
    c=following_for('damped',12)
    assert math.isclose(c.position_gain,.64,abs_tol=1e-12)
    assert math.isclose(c.velocity_gain,.832,abs_tol=1e-12)
    assert c.time_headway_s==1.2 and c.standstill_gap_m==6


def test_smt_obligations_and_nonvacuous_controls(tmp_path):
    result=prove(tmp_path/'proof')
    assert len(result['obligations'])==12 and len(result['negative_controls'])==5
    assert all(v['result']=='unsat' for v in result['obligations'].values())


def test_boundary_and_outside_contract_diagnostics():
    r=boundary()
    assert r['boundary_cases']==2160 and r['excluded_unsafe_cutin']['minimum_gap_m']<0


@pytest.mark.parametrize('profile',['dual_blackout','admissible_cutin','adversarial_nominal','permanent_blackout'])
def test_causal_reference_episode_and_semantic_tamper(profile,tmp_path):
    from .study import run_episode
    out=tmp_path/profile
    result=run_episode(out,profile,12,4001)
    assert result['passed'] and result['ticks']==800
    rows=[json.loads(line) for line in (out/'ticks.jsonl').read_text().splitlines()]
    rows[0]['certificate']['boundary']='9999'
    (out/'ticks.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(AssertionError):check_episode(out)
