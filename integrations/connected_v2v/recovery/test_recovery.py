from dataclasses import asdict
import json
import numpy as np
import pytest
from integrations.connected_v2v import Beacon, V2VEndpoint, encode_beacon
from integrations.connected_v2v.demo import digest
from .controller import FusionFollower, RangeObservation
from .study import run_episode
from .verify import replay

EGO = (0., 0., 0., 12., 0., 0.)


def radar(stamp=0., sequence=0, gap=20.4, target='leader'):
    return RangeObservation(target, sequence, stamp, EGO, gap, 0.)


def ready(method='fusion'):
    node = V2VEndpoint('follower')
    node.observe_local(EGO, 0., 0.)
    return node, FusionFollower(node, 'leader', method=method)


def test_independent_fresh_radar_can_replace_stale_v2v_without_refreshing_it():
    node, controller = ready()
    message = encode_beacon(Beacon('leader', 4, 0., (25.,0.,0.,12.,0.,0.)))
    assert node.receive(message, 0.)
    node.observe_local(EGO, .5, .5)
    assert controller.observe_radar(radar(.5), .5)
    command, info = controller.decide(.5)
    assert info['sensor_source'] == 'radar' and info['selected_observed_s'] == .5
    assert command.accel == pytest.approx(0., abs=1e-12)
    assert node.inbox.latest['leader'].observed_s == 0. and node.peers(.5)['leader']['status'] == 'stale'


@pytest.mark.parametrize('method', ['v2v_only', 'radar_acc', 'fusion'])
def test_missing_all_knowledge_keeps_maximum_braking(method):
    node, controller = ready(method)
    command, info = controller.decide(0.)
    assert command.accel == -6. and info['source'] == 'fallback_brake'
    assert info['sensor_source'] == 'none'


def test_radar_acc_does_not_use_radio_and_radio_only_does_not_use_radar():
    node, radar_acc = ready('radar_acc')
    node.receive(encode_beacon(Beacon('leader',0,0.,(25.,0.,0.,12.,0.,0.))),0.)
    assert radar_acc.decide(0.)[0].accel == -6.
    node, radio_only = ready('v2v_only')
    radio_only.observe_radar(radar(), 0.)
    assert radio_only.decide(0.)[0].accel == -6.


def test_disagreeing_fresh_sources_cannot_hide_a_close_obstacle():
    node, controller = ready()
    node.receive(encode_beacon(Beacon('leader',0,0.,(100.,0.,0.,12.,0.,0.))),0.)
    controller.observe_radar(radar(gap=3.),0.)
    command, info = controller.decide(0.)
    assert command.accel == -6. and info['sensor_source'] == 'disagreement'


def test_expired_future_replayed_and_regressed_radar_samples_are_rejected():
    _, controller = ready()
    assert not controller.observe_radar(radar(.1),0.)
    assert controller.observe_radar(radar(.2,4),.2)
    assert not controller.observe_radar(radar(.3,3),.3)
    assert not controller.observe_radar(radar(.1,5),.3)
    assert not controller.observe_radar(radar(.1,6),.5)
    assert controller.radar['leader'].sequence == 4


def test_stale_ego_forces_hold_brake_despite_fresh_external_sensors():
    node, controller = ready()
    controller.observe_radar(radar(.3),.3)
    command, info = controller.decide(.3)
    assert command.accel == -6. and info['source'] == 'hold_brake' and info['sensor_source'] == 'none'


def test_radar_ttl_is_not_extended_to_the_radio_ttl():
    node, controller = ready()
    controller.observe_radar(radar(),0.)
    node.observe_local(EGO,.25,.25)
    assert controller.decide(.25)[0].accel == -6.


def test_explicit_handover_does_not_follow_old_predecessor_or_reset_replay_state():
    node, controller = ready()
    message = encode_beacon(Beacon('leader',5,0.,(25.,0.,0.,12.,0.,0.)))
    node.receive(message,0.);controller.observe_radar(radar(sequence=4),0.)
    controller.decide(0.);controller.retarget('cut-in')
    assert controller.decide(0.)[0].accel == -6.
    assert not node.receive(message,0.)
    controller.retarget('leader')
    assert not controller.observe_radar(radar(sequence=3),0.)
    assert controller.decide(0.)[1]['sensor_source'] == 'v2v'


def test_measurement_reconstructs_at_source_time_not_receipt_time():
    packet = radar(.1).packet(ready()[1].cfg)
    assert packet.observed_s == .1 and packet.state[0] == pytest.approx(25.)


@pytest.mark.parametrize('method',['v2v_only','radar_acc','fusion'])
def test_closed_loop_sensor_control_and_motion_replay(tmp_path,method):
    summary = run_episode(tmp_path/method,'nominal',method,12.,42,seconds=4.)
    assert summary['vehicle_ticks'] == 240
    assert replay(tmp_path/method)['passed']


def test_auditor_rejects_rehashed_physics_corruption(tmp_path):
    path = tmp_path/'run'
    run_episode(path,'nominal','fusion',12.,42,seconds=4.)
    rows=[json.loads(s) for s in (path/'ticks.jsonl').read_text().splitlines()]
    rows[0]['after']['follower-1'][0] += .1
    (path/'ticks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary=json.loads((path/'summary.json').read_text())
    summary['raw_sha256']=digest(path/'ticks.jsonl')
    (path/'summary.json').write_text(json.dumps(summary))
    with pytest.raises(AssertionError, match='Physics replay mismatch'):
        replay(path)


def test_frozen_gate_rejects_a_single_candidate_collision_or_progress_loss():
    from .campaign import assess
    from .study import SCENARIOS
    rows=[]
    for seed in [1,2,3]:
        for speed in [8.,12.,16.]:
            for scenario in SCENARIOS:
                for method,score in [('v2v_only',1.),('radar_acc',.4),('fusion',.3)]:
                    rows.append(dict(seed=seed,speed=speed,scenario=scenario,method=method,
                        spacing_rms_m=score,jerk_rms_m_s3=1.,collision_pair_ticks=0,corridor_ticks=0,
                        stale_source_ticks=0,bound_violations=0,min_gap_m=5.,
                        progress_m={'follower-1':100.,'follower-2':100.}))
    assert assess(rows)['passed']
    rows[-1]['collision_pair_ticks']=1
    assert not assess(rows)['passed']
    rows[-1]['collision_pair_ticks']=0
    rows[-1]['progress_m']['follower-1']=98.
    assert not assess(rows)['passed']
