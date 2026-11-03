from .native import prepare
import math
import pytest
from .native_vehicle import local_state, scan_from_native


def test_native_project_uses_real_devices_and_has_no_target_truth_interface(tmp_path):
    world = prepare(tmp_path/'native', 73)
    text = world.read_text()
    source = (tmp_path/'native/project/controllers/autonomous_vehicle/autonomous_vehicle.py').read_text()
    assert text.count('size 2000 100 0.2') == 2
    assert text.count('name "local_radar"') == 3
    assert text.count('Emitter {') == text.count('Receiver {') == 3
    assert 'randomSeed 73' in text
    assert 'getFromDef' not in source and 'getPosition' not in source and '.retarget(' not in source
    assert 'getTargets()' in source and 'getBytes()' in source
    compile(source, 'autonomous_vehicle.py', 'exec')


def test_invalid_native_return_marks_scan_incomplete_instead_of_crashing_or_claiming_clear():
    for speed in (None, float('nan'), 100.):
        scan = scan_from_native(0, 0., (0., 0., 0., 0., 0., 0.),
                                [dict(distance=25., azimuth=0., speed=speed)])
        assert not scan.complete and not scan.detections


def test_native_axes_preserve_left_positive_bearing_and_body_lateral_velocity():
    scan = scan_from_native(0, 0., (0., 0., 0., 0., 0., 0.),
                            [dict(distance=25., azimuth=-.1, speed=0.)])
    assert scan.detections[0].azimuth_rad == .1
    heading = .2
    vector = (8.*math.cos(heading)-math.sin(heading), 8.*math.sin(heading)+math.cos(heading), 0.)
    state = local_state((0., 0., 0.), heading, vector, .1)
    assert state[3:5] == pytest.approx([8., 1.])
