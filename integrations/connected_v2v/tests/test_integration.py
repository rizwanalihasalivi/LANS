import pytest
from integrations.connected_v2v import Beacon, V2VEndpoint, encode_beacon
from integrations.unified_lans.controller import Pipeline
from integrations.unified_lans.physics import Route
from integrations.connected_v2v.demo import run_case

EGO = (0., .1, 0., 10., 0., 0.)


def packet(name, stamp=0., sequence=0, x=50., speed=10.):
    return encode_beacon(Beacon(name, sequence, stamp, (x, 0., 0., speed, 0., 0.)))


def test_discovered_multiple_peers_reach_existing_critical_vehicle_supervisor():
    pipe = Pipeline(Route(), mode='lqr')
    node = V2VEndpoint('car-a', inbox=pipe.inbox)
    node.observe_local(EGO, 0., 0.)
    assert node.receive(packet('far', x=100., speed=15.), 0.)
    assert node.receive(packet('near', x=12., speed=0.), 0.)
    node.sync_expected(pipe)
    result = pipe.decide(0.)
    assert pipe.expected == {'far', 'near'}
    assert result['critical_id'] == 'near' and result['risk'] == 'DANGER'
    assert result['issued_accel'] == -pipe.cfg.max_brake


def test_one_fresh_peer_cannot_hide_another_peer_dropout_and_return():
    pipe = Pipeline(Route(), mode='hybrid')
    node = V2VEndpoint('car-a', inbox=pipe.inbox)
    node.observe_local(EGO, 0., 0.)
    for name in ['car-b', 'car-c']:
        assert node.receive(packet(name), 0.)
    node.observe_local(EGO, .5, .5)
    assert node.receive(packet('car-c', stamp=.5, sequence=1), .5)
    node.sync_expected(pipe)
    result = pipe.decide(.5)
    assert result['missing'] == ['car-b'] and result['risk'] == 'DANGER'
    assert result['source'] == 'lqr' and result['issued_accel'] == -pipe.cfg.max_brake
    assert node.receive(packet('car-b', stamp=.5, sequence=1), .5)
    assert pipe.decide(.5)['missing'] == []


def test_predeclared_peer_is_missing_until_a_valid_message_arrives():
    pipe = Pipeline(Route(), mode='lqr')
    node = V2VEndpoint('car-a', inbox=pipe.inbox, expected_peers=['car-b'])
    node.observe_local(EGO, 0., 0.); node.sync_expected(pipe)
    assert node.peers(0.)['car-b']['status'] == 'missing'
    assert pipe.decide(0.)['missing'] == ['car-b']
    assert node.receive(packet('car-b'), 0.)
    assert pipe.decide(0.)['missing'] == []


def test_attachment_refuses_inconsistent_inboxes_rosters_or_ttls():
    pipe = Pipeline(Route())
    node = V2VEndpoint('car-a')
    with pytest.raises(ValueError, match='share'):
        node.sync_expected(pipe)
    node = V2VEndpoint('car-a', inbox=pipe.inbox, max_packet_age_s=.2)
    with pytest.raises(ValueError, match='thresholds'):
        node.sync_expected(pipe)
    node = V2VEndpoint('car-a', inbox=pipe.inbox)
    pipe.expected = {'unknown'}
    with pytest.raises(ValueError, match='outside'):
        node.sync_expected(pipe)


@pytest.mark.parametrize('case', ['nominal', 'peer_blackout', 'late_join'])
def test_fleet_demo_exercises_multi_peer_fallback_and_discovery(tmp_path, case):
    summary = run_case(case, 2.5, 42, tmp_path/case)
    assert summary['control_ticks'] >= 150 and summary['delivery_events'] > 0
    if case == 'peer_blackout':
        assert summary['stale_fallback_vehicle_ticks'] > 0
        assert summary['endpoints']['vehicle-a']['peers']['vehicle-b']['status'] == 'fresh'
    elif case == 'late_join':
        assert 'vehicle-d' in summary['endpoints']['vehicle-a']['peers']
    with pytest.raises(FileExistsError):
        run_case(case, 2.5, 42, tmp_path/case)
