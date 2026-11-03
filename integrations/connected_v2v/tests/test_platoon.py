import pytest
from integrations.connected_v2v import Beacon, V2VEndpoint, encode_beacon
from integrations.connected_v2v.platoon import PlatoonController
from integrations.connected_v2v.platoon_demo import run_case


def ready(gap=20.4, speed=12., predecessor_speed=12.):
    node = V2VEndpoint('follower', expected_peers=['leader'])
    node.observe_local([0., 0., 0., speed, 0., 0.], 0., 0.)
    node.receive(encode_beacon(Beacon('leader', 0, 0., (gap+4.6, 0., 0., predecessor_speed, 0., 0.))), 0.)
    return node, PlatoonController(node, 'leader')


def test_equilibrium_and_response_to_leader_braking_use_received_state():
    node, controller = ready()
    command, decision = controller.decide(0.)
    assert command.accel == pytest.approx(0., abs=1e-12)
    assert decision['gap_m'] == pytest.approx(decision['desired_gap_m'])
    node.receive(encode_beacon(Beacon('leader', 1, 0., (25., 0., 0., 9., 0., 0.))), 0.)
    command, decision = controller.decide(0.)
    assert command.accel < 0. and decision['source'] == 'cooperative_following'


def test_expired_predecessor_brakes_even_when_local_ego_is_fresh():
    node, controller = ready()
    node.observe_local([0., 0., 0., 12., 0., 0.], .5, .5)
    command, decision = controller.decide(.5)
    assert command.accel == -6. and decision['source'] == 'fallback_brake'
    assert decision['missing'] == ['leader']


def test_missing_ego_does_not_create_a_fabricated_control_state():
    node, controller = ready()
    command, decision = controller.decide(.25)
    assert decision['source'] == 'hold_brake' and command.accel == -6.


def test_invalid_predecessor_and_external_follower_schedule_are_refused():
    node = V2VEndpoint('follower')
    with pytest.raises(ValueError):
        PlatoonController(node, 'leader')
    _, controller = ready()
    with pytest.raises(ValueError):
        controller.decide(0., leader_accel=2.)


def test_cooperative_demo_preserves_gap_and_exercises_blackout_recovery(tmp_path):
    summary = run_case('predecessor_blackout', 4., 42, tmp_path/'run')
    assert summary['vehicle_ticks'] == 240
    assert summary['fallback_vehicle_ticks'] > 0
    assert summary['min_true_gap_m'] > 0 and summary['collision_follower_ticks'] == 0
