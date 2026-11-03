import math
import numpy as np
import pytest
from integrations.connected_v2v.messages import Beacon, encode_beacon
from integrations.connected_v2v.node import V2VEndpoint
from .controller import AutonomousFollower, Detection, Scan
from .road import Road


EGO = (0., 0., 0., 12., 0., 0.)


def ready(**kwargs):
    node = V2VEndpoint('follower')
    node.observe_local(EGO, 0., 0.)
    return node, AutonomousFollower(node, **kwargs)


def radio(node, name, x, y=0., *, now=0., sequence=0, speed=12.):
    return node.receive(encode_beacon(Beacon(name, sequence, now, (x, y, 0., speed, 0., 0.))), now)


def scan(positions=((25., 0.),), *, now=0., sequence=0, complete=True):
    returns = tuple(Detection(math.hypot(x, y), math.atan2(y, x), 0.) for x, y in positions)
    return Scan(sequence, now, EGO, returns, complete)


def test_startup_without_knowledge_does_not_cruise():
    _, control = ready()
    command, info = control.decide(0.)
    assert command.accel == -6. and info['selection_brake']


def test_nearest_in_lane_radio_is_discovered_without_membership_commands():
    node, control = ready()
    radio(node, 'far', 50.)
    radio(node, 'near', 25.)
    radio(node, 'adjacent', 18., 3.5)
    command, info = control.decide(0.)
    assert info['selected_target'] == control.aliases['near']
    assert info['selection_event'] == 'acquired'
    assert command.accel == pytest.approx(0., abs=1e-12)


def test_anonymous_nonconnected_return_is_followed_without_a_radio_identity():
    node, control = ready()
    assert control.observe_scan(scan(), 0.)
    command, info = control.decide(0.)
    assert not node.expected and info['selected_target'] == 'track-1'
    assert info['sensor_source'] == 'radar' and command.accel == pytest.approx(0., abs=1e-12)


def test_unique_radio_radar_association_preserves_both_original_timestamps():
    node, control = ready()
    radio(node, 'front', 25.)
    control.observe_scan(scan(), 0.)
    control.decide(0.)
    node.observe_local(EGO, .05, .05)
    command, info = control.decide(.05)
    assert info['selected_target'] == control.aliases['front']
    assert control.follower.radar[control.selected].observed_s == 0.
    assert control.local.inbox.latest[control.selected].observed_s == 0.
    assert command.accel > -6.


def test_radio_silence_cannot_release_to_farther_target_or_reset_replay_watermark():
    node, control = ready()
    radio(node, 'front', 25., sequence=5)
    control.decide(0.)
    for i in range(1, 5):
        now = i*.2
        node.observe_local(EGO, now, now)
        radio(node, 'far', 60., now=now, sequence=i)
        command, info = control.decide(now)
    assert info['selected_target'] == control.aliases['front'] and command.accel == -6.
    assert not radio(node, 'front', 25., now=.8, sequence=4)


def test_new_peer_nearer_than_last_known_gap_cannot_hide_an_unobserved_old_target():
    node, control = ready()
    radio(node, 'front', 25.)
    control.decide(0.)
    # The old target might have stopped and become closer during the blackout.
    # Its last gap is not current positive evidence of its ordering/departure.
    node.observe_local(EGO, .5, .5)
    radio(node, 'new-peer', 20., now=.5)
    command, info = control.decide(.5)
    assert info['selected_target'] == control.aliases['front']
    assert info['selection_brake'] and command.accel == -6.


def test_closer_cut_in_is_immediate_but_farther_cut_out_needs_distinct_complete_scans():
    node, control = ready()
    control.observe_scan(scan(((50., 0.),)), 0.)
    control.decide(0.)
    node.observe_local(EGO, .1, .1)
    control.observe_scan(scan(((50., 0.), (25., 0.)), now=.1, sequence=1), .1)
    _, info = control.decide(.1)
    assert info['selection_event'] == 'cut_in'
    old = control.selected
    for i in range(2, 5):
        now = i*.1
        node.observe_local(EGO, now, now)
        control.observe_scan(scan(((50., 0.),), now=now, sequence=i), now)
        _, info = control.decide(now)
        if i < 4:
            assert info['selection_brake'] and control.selected == old
            control.decide(now)  # Calling decide twice is not a second sensor frame.
    assert info['selection_event'] == 'cut_out' and control.selected != old


def test_empty_incomplete_or_stale_scan_cannot_grant_clear_road():
    node, control = ready()
    for i in range(4):
        now = i*.1
        node.observe_local(EGO, now, now)
        control.observe_scan(scan((), now=now, sequence=i, complete=False), now)
        assert control.decide(now)[0].accel == -6.
    for i in range(4, 7):
        now = i*.1
        node.observe_local(EGO, now, now)
        control.observe_scan(scan((), now=now, sequence=i), now)
        command, _ = control.decide(now)
    assert command.accel >= 0.
    node.observe_local(EGO, 1., 1.)
    assert control.decide(1.)[0].accel == -6.


@pytest.mark.parametrize('kind', ['ambiguous_identity', 'duplicate_return', 'speed_disagreement'])
def test_association_ambiguity_or_disagreement_brakes(kind):
    node, control = ready()
    radio(node, 'front', 25., speed=20. if kind == 'speed_disagreement' else 12.)
    if kind == 'ambiguous_identity':
        radio(node, 'impostor', 25.2)
    control.observe_scan(scan(), 0.)
    if kind == 'duplicate_return':
        node.observe_local(EGO, .1, .1)
        control.observe_scan(scan(((26.2, 0.), (26.3, 0.)), now=.1, sequence=1), .1)
    command, info = control.decide(.1 if kind == 'duplicate_return' else 0.)
    assert command.accel == -6. and info['selection_event'] == 'association_ambiguous'


def test_stale_future_duplicate_and_regressed_scans_are_rejected():
    _, control = ready()
    assert not control.observe_scan(scan(now=.1), 0.)
    assert control.observe_scan(scan(now=.1, sequence=4), .1)
    assert not control.observe_scan(scan(now=.2, sequence=4), .2)
    assert not control.observe_scan(scan(now=.05, sequence=5), .2)
    assert not control.observe_scan(scan(now=.1, sequence=6), .5)
    assert control.scan.sequence == 4 and control.rejected_scans == 4


def test_stale_ego_is_not_refreshed_by_external_observations():
    node, control = ready()
    radio(node, 'front', 30., now=.3)
    command, info = control.decide(.3)
    assert command.accel == -6. and info['source'] == 'hold_brake'


def test_curved_map_projects_target_without_reading_a_predecessor_label():
    road = Road(500.)
    node, control = ready(road=road)
    position = road.position(25.)
    node.receive(encode_beacon(Beacon('front', 0, 0., (*position, .05, 12., 0., .024))), 0.)
    distance = float(np.linalg.norm(position))
    # Target speed is tangent to the circle, not assumed equal to range-rate.
    ray = position/distance
    rate = float((12.*np.array([math.cos(.05), math.sin(.05)])-np.array([12., 0.]))@ray)
    control.observe_scan(Scan(0, 0., EGO, (Detection(distance, math.atan2(position[1], position[0]), rate),)), 0.)
    command, info = control.decide(0.)
    assert info['selected_target'] == control.aliases['front']
    assert command.accel == pytest.approx(0., abs=1e-10)
    assert command.steering > 0.


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, -1., 121.])
def test_invalid_sensor_values_fail_before_tracking(value):
    with pytest.raises(ValueError):
        Detection(value, 0., 0.)


def test_capacity_exhaustion_brakes_and_does_not_evict_replay_state():
    node = V2VEndpoint('follower', max_peers=1)
    node.observe_local(EGO, 0., 0.)
    control = AutonomousFollower(node)
    control.observe_scan(scan(), 0.)
    control.decide(0.)
    node.observe_local(EGO, .1, .1)
    control.observe_scan(scan(((25., 0.), (50., 0.)), now=.1, sequence=1), .1)
    assert control.decide(.1)[0].accel == -6.
    assert len(control.tracks) == 1


def test_adjacent_slow_vehicle_limits_catch_up_before_its_lane_intent_is_known():
    node, control = ready()
    node.observe_local((0., 0., 0., 18., 0., 0.), 0., 0.)
    radio(node, 'leader', 70., speed=12.)
    radio(node, 'adjacent', 20., 3.5, speed=10.5)
    command, info = control.decide(0.)
    assert info['selected_target'] == control.aliases['leader']
    assert info['nearby_stopping_guard'] and command.accel == -6.
