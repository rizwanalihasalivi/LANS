from dataclasses import replace
import pytest
from integrations.connected_v2v.autonomy.test_controller import EGO,ready,radio,scan
from .controller import RobustFollower


def robust():
    node,_=ready()
    return node,RobustFollower(node)


def test_repeated_missed_detections_cannot_fabricate_departure():
    node,control=robust()
    control.observe_scan(scan(),0.);control.decide(0.)
    old=control.selected
    for i in range(1,11):
        now=i*.1;node.observe_local(EGO,now,now)
        radio(node,'far',70.,now=now,sequence=i)
        control.observe_scan(scan((),now=now,sequence=i),now)
        command,info=control.decide(now)
        assert control.selected==old and command.accel==-6.
        assert not info['absence_is_departure']


def test_anonymous_target_reacquires_after_burst_without_extending_control_ttl():
    node,control=robust()
    control.observe_scan(scan(),0.);control.decide(0.)
    old=control.selected
    node.observe_local(EGO,.5,.5)
    assert control.decide(.5)[0].accel==-6.
    node.observe_local(EGO,1.,1.)
    control.observe_scan(scan(((37.,0.),),now=1.,sequence=10),1.)
    command,info=control.decide(1.)
    assert control.selected==old and len(control.tracks)==1
    assert info['selected_observed_s']==1. and command.accel>-6.
    assert not control.observe_scan(scan(now=1.,sequence=9),1.)


def test_positive_anonymous_exit_releases_with_no_old_radio_identity():
    node,control=robust()
    control.observe_scan(scan(),0.);control.decide(0.)
    old=control.selected
    for i in range(1,9):
        now=i*.1;node.observe_local(EGO,now,now)
        radio(node,'far',70.,now=now,sequence=i)
        control.observe_scan(scan(((25.+12.*now,min(3.5,i*.5)),),now=now,sequence=i),now)
        command,info=control.decide(now)
    assert control.selected!=old and control.selected==control.aliases['far']
    assert info['positive_exit_frames']>=3 or info['positive_exit_target']!=old


def test_unknown_empty_road_does_not_become_a_cruise_permission():
    node,control=robust()
    for i in range(5):
        now=i*.1;node.observe_local(EGO,now,now)
        control.observe_scan(scan((),now=now,sequence=i),now)
        assert control.decide(now)[0].accel==-6.


def test_late_radio_identity_promotes_same_anonymous_object_without_deadlock():
    node,control=robust()
    control.observe_scan(scan(),0.);control.decide(0.)
    radio(node,'front',25.,now=.05)
    node.observe_local(EGO,.05,.05)
    control.decide(.05)
    node.observe_local(EGO,.1,.1)
    command,info=control.decide(.1)
    assert control.selected==control.aliases['front'] and command.accel>-6.


def test_radio_following_does_not_lose_a_fresh_target_at_the_radar_range_boundary():
    node,control=robust()
    radio(node,'front',130.)
    command,info=control.decide(0.)
    assert control.selected==control.aliases['front'] and info['sensor_source']=='v2v'
    assert command.accel>0.


def test_adjacent_lane_noise_derivative_is_not_an_observed_cut_in():
    assert not RobustFollower._in_lane(25.,3.5,-5.,0.)
    assert RobustFollower._in_lane(25.,2.3,-2.,0.)


def test_dormant_wide_gate_does_not_deadlock_an_unambiguous_fresh_match():
    from integrations.connected_v2v.autonomy.controller import Track
    node,control=robust()
    control.tracks={'track-1':Track('track-1',1.,30.,0.,12.,0.,10,'track-1'),
                    'track-2':Track('track-2',0.,20.,0.,10.,0.,0,'track-2')}
    control.observe_scan(scan(((31.2,0.),),now=1.1,sequence=11),1.1)
    assert not control.scan_fault and [t.name for t in control.active]==['track-1']


def test_track_matches_are_invariant_to_return_order():
    values=[]
    for positions in [((26.2,0.),(51.2,0.)),((51.2,0.),(26.2,0.))]:
        node,control=robust();control.observe_scan(scan(((25.,0.),(50.,0.))),0.)
        control.observe_scan(scan(positions,now=.1,sequence=1),.1)
        values.append(sorted((t.name,t.s) for t in control.active))
    assert values[0]==values[1]
