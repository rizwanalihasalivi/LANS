import json
import math
import pytest
from integrations.connected_v2v.messages import Beacon, decode_beacon, encode_beacon, MAX_MESSAGE_BYTES
from integrations.connected_v2v.node import V2VEndpoint

STATE = (10., .2, .01, 8., 0., 0.)


def message(**updates):
    value = dict(version=1, vehicle_id='car-b', sequence=4, observed_s=.1, state=list(STATE))
    value.update(updates)
    return json.dumps(value).encode()


def test_wire_round_trip_copies_mutable_state_and_preserves_observation():
    state = list(STATE)
    beacon = Beacon('car-a', 2, .1, state)
    state[0] = -100.
    decoded = decode_beacon(encode_beacon(beacon))
    assert decoded == beacon and decoded.state == STATE and decoded.observed_s == .1


@pytest.mark.parametrize('updates', [
    {'version': True}, {'version': 2}, {'extra': 1}, {'vehicle_id': []},
    {'vehicle_id': 'ego'}, {'vehicle_id': 'not a vehicle'}, {'vehicle_id': 'x'*65},
    {'sequence': True}, {'sequence': -1}, {'sequence': 2**63},
    {'observed_s': True}, {'observed_s': -1}, {'observed_s': math.inf},
    {'state': None}, {'state': [0]*5}, {'state': [0, 0, 0, -1, 0, 0]},
    {'state': [0, 0, 0, True, 0, 0]}, {'state': [0, 0, 0, math.nan, 0, 0]},
])
def test_malformed_beacons_are_rejected_without_mutating_inbox(updates):
    endpoint = V2VEndpoint('car-a')
    assert not endpoint.receive(message(**updates), .2)
    assert not endpoint.expected and not endpoint.inbox.latest
    assert endpoint.rejections == {'malformed': 1}


@pytest.mark.parametrize('payload', [b'', b'\xff', b'[]', b'null', b'{', b' '* (MAX_MESSAGE_BYTES+1),
                                     b'{"version":1,"version":1}', 'not bytes'])
def test_bounded_json_and_duplicate_field_validation(payload):
    with pytest.raises(ValueError):
        decode_beacon(payload)


def test_different_sources_have_independent_replay_counters():
    endpoint = V2VEndpoint('car-a')
    assert endpoint.receive(message(sequence=100), .2)
    assert endpoint.receive(message(vehicle_id='car-c', sequence=0), .2)
    assert endpoint.expected == {'car-b', 'car-c'}


def test_replay_and_timestamp_regression_cannot_refresh_cached_information():
    endpoint = V2VEndpoint('car-a')
    assert endpoint.receive(message(sequence=10), .2)
    for payload in [message(sequence=10), message(sequence=9), message(sequence=11, observed_s=.05)]:
        assert not endpoint.receive(payload, .3)
    peer = endpoint.peers(.4)['car-b']
    assert peer['observed_s'] == .1 and peer['received_s'] == .2
    assert peer['age_s'] == pytest.approx(.3)
    assert endpoint.rejections == {'replay_or_regression': 3}


def test_future_or_expired_first_contact_does_not_discover_a_peer():
    endpoint = V2VEndpoint('car-a')
    assert not endpoint.receive(message(observed_s=.6), .5)
    assert not endpoint.receive(message(observed_s=0.), .5)
    assert endpoint.expected == frozenset()
    assert endpoint.rejections == {'future': 1, 'expired_on_arrival': 1}


def test_stale_contacts_remain_expected_and_recovery_preserves_replay_watermark():
    endpoint = V2VEndpoint('car-a')
    assert endpoint.receive(message(sequence=5, observed_s=0.), 0.)
    assert endpoint.peers(.5)['car-b']['status'] == 'stale'
    assert endpoint.expected == {'car-b'}
    assert not endpoint.receive(message(sequence=0, observed_s=.5), .5)
    assert endpoint.receive(message(sequence=6, observed_s=.5), .5)
    assert endpoint.peers(.5)['car-b']['status'] == 'fresh'


def test_unknown_peer_capacity_is_bounded_without_evicting_existing_contact():
    endpoint = V2VEndpoint('car-a', max_peers=1)
    assert endpoint.receive(message(), .1)
    assert not endpoint.receive(message(vehicle_id='car-c'), .1)
    assert endpoint.rejections['peer_capacity'] == 1
    assert endpoint.receive(message(sequence=5, observed_s=.2), .2)
    assert len(endpoint.inbox.latest) == 1 and endpoint.expected == {'car-b'}


def test_external_sender_cannot_replace_local_ego_slot():
    endpoint = V2VEndpoint('car-a')
    endpoint.observe_local(STATE, 0., 0.)
    assert not endpoint.receive(message(vehicle_id='ego'), .1)
    assert not endpoint.receive(message(vehicle_id='car-a'), .1)
    assert endpoint.inbox.latest['ego'].state == STATE
    assert not endpoint.expected


def test_clock_or_local_observation_regression_is_an_explicit_error():
    endpoint = V2VEndpoint('car-a')
    endpoint.observe_local(STATE, .2, .2)
    with pytest.raises(ValueError, match='backwards'):
        endpoint.receive(message(), .1)
    with pytest.raises(ValueError, match='regressed'):
        endpoint.observe_local(STATE, .1, .3)
    assert endpoint.inbox.latest['ego'].observed_s == .2
