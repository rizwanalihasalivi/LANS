"""Adversarial regressions found in the post-release V2V audit."""
import json
import math
import importlib
import sys

import pytest

from integrations.connected_v2v.autonomy.controller import AutonomousFollower, Detection, Scan
from integrations.connected_v2v.autonomy.test_controller import EGO, radio, scan
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.robustness.controller import RobustFollower
from integrations.connected_v2v.robustness.perception import encode_peer_scan
from integrations.connected_v2v.settling.controller import SettlingFollower
from integrations.connected_v2v.settling.certify import native_refinement
from integrations.connected_v2v.settling.trace_certificate import certificate


@pytest.mark.parametrize('controller', [AutonomousFollower, RobustFollower, SettlingFollower])
@pytest.mark.parametrize('name', ['peer-1', 'track-1'])
def test_wire_identity_cannot_collide_with_internal_target_alias(controller, name):
    node = V2VEndpoint(name)
    node.observe_local(EGO, 0., 0.)
    control = controller(node)
    if name == 'peer-1':
        radio(node, 'front', 50.)
    else:
        control.observe_scan(scan(), 0.)
    command, info = control.decide(0.)
    assert info['sensor_source'] in ('v2v', 'radar')
    assert command.accel > -6.


@pytest.mark.parametrize('controller', [AutonomousFollower, RobustFollower, SettlingFollower])
def test_retired_unselected_tracks_do_not_exhaust_lifetime_capacity(controller):
    node = V2VEndpoint('follower', max_peers=2)
    control = controller(node)
    names = set()
    for i in range(40):
        now = i * 3.
        node.observe_local(EGO, now, now)
        control.observe_scan(scan(((50., 3.5),), now=now, sequence=i), now)
        control.decide(now)
        assert not control.scan_fault
        assert len(control.tracks) <= 2
        assert len(control.active) == 1
        name = control.active[0].name
        assert name not in names, 'retired anonymous identities must never be reused'
        names.add(name)


@pytest.mark.parametrize('controller', [RobustFollower, SettlingFollower])
def test_pruning_never_releases_an_unobserved_selected_target(controller):
    node = V2VEndpoint('follower', max_peers=2)
    control = controller(node)
    node.observe_local(EGO, 0., 0.)
    control.observe_scan(scan(), 0.)
    control.decide(0.)
    old = control.selected
    for i in range(1, 6):
        now = i * 3.
        node.observe_local(EGO, now, now)
        control.observe_scan(scan(((50., 3.5),), now=now, sequence=i), now)
        command, info = control.decide(now)
        assert control.selected == old and old in control.tracks
        assert command.accel == -6. and info['selection_brake']
        assert not control.scan_fault


def test_source_fallback_does_not_recount_an_older_confirmation():
    node = V2VEndpoint('follower')
    control = SettlingFollower(node)
    for now in (0., .1, .15, .36, .37):
        node.observe_local(EGO, now, now)
        if now == 0.:
            radio(node, 'leader', 80., now=now)
        if now == .1:
            radio(node, 'intruder', 50., now=now)
        if now == .15:
            control.observe_scan(scan(((50.6, 0.),), now=now), now)
        _, info = control.decide(now)
    assert info['selected_observed_s'] == .1
    assert info['confirmed_following_frames'] == 2
    assert info['lateral_guard_mode'] == 'conservative'


def test_settling_requires_elapsed_time_and_contiguous_control_observations():
    node = V2VEndpoint('follower')
    control = SettlingFollower(node)
    control.recovering = True
    node.observe_local(EGO, 0., 0.)
    radio(node, 'head', 25.)
    for _ in range(50):
        control.decide(0.)
    assert control.recovering, 'repeated calls cannot manufacture two seconds'
    for i in range(1, 41):
        now = i * .05
        node.observe_local(EGO, now, now)
        radio(node, 'head', 25., now=now, sequence=i)
        control.decide(now)
        if now < 2.:
            assert control.recovering
    assert not control.recovering
    control.recovering = True
    for now, sequence in ((3., 41), (6., 42)):
        node.observe_local(EGO, now, now)
        radio(node, 'head', 25., now=now, sequence=sequence)
        control.decide(now)
        assert control.recovering, 'unobserved gaps cannot count as stable time'


@pytest.mark.parametrize('controller', [RobustFollower, SettlingFollower])
def test_peer_scan_rejects_contradictory_heading_even_when_stationary(controller):
    node = V2VEndpoint('follower')
    control = controller(node)
    radio(node, 'observer', 0., speed=0.)
    bad = Scan(0, 0., (0., 0., math.pi, 0., 0., 0.), (Detection(30., 0., 0.),), False)
    assert not control.observe_peer_scan(encode_peer_scan('observer', bad), 0.)
    good = Scan(0, 0., (0., 0., 2 * math.pi, 0., 0., 0.), (), False)
    assert control.observe_peer_scan(encode_peer_scan('observer', good), 0.)


@pytest.mark.parametrize('duration', [-.05, 0., float('nan'), float('inf'), True])
def test_trace_certificate_rejects_invalid_time_interval(duration):
    with pytest.raises(ValueError):
        certificate((0., 0., 0.), (0., 0., 0.), (0., 2., 0.), (0., 2., 0.), duration)


def native_fixture(tmp_path):
    spec = dict(starts={'follower': (0., 0.)}, profile={'radius': 0.}, seconds=.1)
    traces = {'follower': [dict(time_s=t, state=[1.4, 0., 0., 0., 0., 0.],
        pose=dict(position=[1.4, 0., .5], rpy=[0., 0., 0.]),
        command={'accel': 0.}, native_speed_cap_m_s=16.) for t in (.05, .1)]}
    motion = [dict(time_s=i * .01, position=[1.4, 0., .5], velocity=[0., 0., 0.],
                   heading=0., yaw_rate=0.) for i in range(1, 11)]
    return spec, traces, motion


@pytest.mark.parametrize('fault', ['last_roll', 'last_pitch_nan', 'first_yaw', 'first_accel'])
def test_native_refinement_checks_boundary_samples(tmp_path, fault):
    spec, traces, motion = native_fixture(tmp_path)
    if fault == 'last_roll':
        traces['follower'][-1]['pose']['rpy'][0] = .2
    elif fault == 'last_pitch_nan':
        traces['follower'][-1]['pose']['rpy'][1] = float('nan')
    elif fault == 'first_yaw':
        motion[0]['yaw_rate'] = 3.
    elif fault == 'first_accel':
        for row in motion:
            row['velocity'][0] = .3  # Initial world speed is zero: 30 m/s² in 10 ms.
    (tmp_path / 'follower-motion.jsonl').write_text(''.join(json.dumps(z) + '\n' for z in motion))
    with pytest.raises((AssertionError, ValueError)):
        native_refinement(tmp_path, spec, traces)


def test_native_refinement_accepts_complete_valid_samples(tmp_path):
    spec, traces, motion = native_fixture(tmp_path)
    (tmp_path / 'follower-motion.jsonl').write_text(''.join(json.dumps(z) + '\n' for z in motion))
    report, _ = native_refinement(tmp_path, spec, traces)
    assert report['follower']['motion_samples'] == 10


@pytest.mark.parametrize('module_name', ['autonomy.native_vehicle', 'robustness.native_vehicle', 'settling.native_vehicle'])
def test_native_receiver_keeps_running_after_non_utf8_packet(tmp_path, monkeypatch, module_name):
    from integrations.connected_v2v.messages import Beacon, encode_beacon
    from integrations.connected_v2v.settling.native import configuration
    module = importlib.import_module('integrations.connected_v2v.' + module_name)
    (tmp_path / 'config.json').write_text(json.dumps(configuration('curved', 8., 6203)))
    monkeypatch.setenv('LANS_ROBUST_OUTPUT', str(tmp_path))
    monkeypatch.setenv('LANS_AUTONOMY_NATIVE_OUTPUT', str(tmp_path))
    monkeypatch.setenv('LANS_AUTONOMY_NATIVE_CASE', 'nominal')
    monkeypatch.setattr(sys, 'argv', ['controller', 'follower'])

    class Device:
        def __init__(self, name):
            self.name = name
            self.messages = [b'\xff'] * 10 + [encode_beacon(Beacon('leader', 0, 0., (50., 0., 0., 0., 0., 0.)))]
        def enable(self, _): pass
        def setChannel(self, _): pass
        def setRange(self, _): pass
        def send(self, _): pass
        def getValues(self): return [0., 0., .5] if self.name == 'local_gps' else [0., 0., 0.]
        def getRollPitchYaw(self): return [0., 0., 0.]
        def getSpeedVector(self): return [0., 0., 0.]
        def getTargets(self): return []
        def getQueueLength(self): return len(self.messages)
        def getBytes(self): return self.messages[0]
        def nextPacket(self): self.messages.pop(0)

    class Driver:
        count = 0
        cruise = 0.
        def getDevice(self, name): return Device(name)
        def step(self):
            self.count += 1
            return 0 if self.count <= 20 else -1
        def getTime(self): return self.count * .01
        def setCruisingSpeed(self, speed): self.cruise = speed
        def setBrakeIntensity(self, _): pass
        def setSteeringAngle(self, _): pass
        def getBrakeIntensity(self): return 0.
        def getControlMode(self): return 0
        def getTargetCruisingSpeed(self): return self.cruise

    module.main(Driver())
    data = [json.loads(line) for line in (tmp_path / 'follower.jsonl').read_text().splitlines()]
    assert len(data) == 4
    rejected = [event for row in data for event in row['radio'] if not event['accepted']]
    assert any(event['message'].encode('utf-8', errors='surrogateescape') == b'\xff' for event in rejected)
