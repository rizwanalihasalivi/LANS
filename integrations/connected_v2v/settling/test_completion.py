import math
from fractions import Fraction as F
import pytest
from .controller import SettlingFollower,lane_guard
from .geometry import CircularRoad,route_steering
from .pacing import pace_goal
from .trace_certificate import trig_bounds,Q,certificate
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.messages import Beacon,encode_beacon,decode_beacon
from .relay import FormationRelays


def test_guard_is_conservative_before_positive_departure():
    adjacent=[(20.,3.5,10.,0.)]
    assert lane_guard(adjacent,0.,20.,False)[0]
    assert not lane_guard(adjacent,0.,20.,True)[0]
    assert lane_guard([(20.,1.,10.,0.)],0.,20.,True)[0]
    assert lane_guard([(20.,3.5,10.,-4.)],0.,20.,True)[0]


def test_full_arc_route_steering_is_finite():
    road=CircularRoad(600.)
    for s in (0.,500.,1100.,1500.):
        p=road.position(s);state=(*p,s/600.,12.,0.,12./600.)
        assert math.isfinite(route_steering(state,road))
        assert abs(route_steering(state,road))<.05


def test_leader_paces_only_from_received_member_state():
    node=V2VEndpoint('head');member=V2VEndpoint('member')
    own=(100.,0.,0.,12.,0.,0.);road=CircularRoad()
    assert pace_goal(node,own,0,road,12,member='member')[0]==8
    wire=member.publish((0.,0.,0.,8.,0.,0.),0,0)
    assert node.receive(wire,0)
    goal,info=pace_goal(node,own,0,road,12,member='member')
    assert goal==8 and info['member_gap_m']==100
    assert node.receive(member.publish((50.,0.,0.,12.,0.,0.),.1,.1),.1)
    assert pace_goal(node,own,.1,road,12,member='member')[0]==12
    assert pace_goal(node,own,1,road,12,member='member')[1]['pacing']=='member_unavailable'


@pytest.mark.parametrize('angle',[-4.,-3.14,-2.,-.1,0.,.1,1.,3.14,4.])
def test_rigorous_taylor_intervals_against_high_precision(angle):
    import mpmath as mp
    mp.mp.dps=70
    sn,cs=trig_bounds(angle)
    for bounds,value in ((sn,mp.sin(str(angle))),(cs,mp.cos(str(angle)))):
        assert mp.mpf(bounds[0])/Q<=value<=mp.mpf(bounds[1])/Q


def test_two_dimensional_continuous_axis_certificate():
    a0=(0.,0.,0.);a1=(.5,0.,0.)
    assert certificate(a0,a1,(10.,0.,0.),(10.5,0.,0.),.05)['margin_um']>0
    assert certificate(a0,a1,(0.,3.5,0.),(.5,3.5,0.),.05)['margin_um']>0
    assert certificate(a0,a1,(0.,0.,0.),(.5,0.,0.),.05) is None
    # Separated endpoints cannot certify an arbitrary excursion without enough
    # acceleration margin. A large interval invalidates the same tight geometry.
    assert certificate(a0,a1,(0.,3.5,0.),(.5,3.5,0.),1.) is None


def test_initial_missing_knowledge_brakes():
    node=V2VEndpoint('ego-car');control=SettlingFollower(node)
    node.observe_local((0.,0.,0.,12.,0.,0.),0,0)
    cmd,info=control.decide(0)
    assert cmd.accel==-6 and info['connectivity_mode']=='knowledge_unavailable'
    assert info['formation_mode']=='following' and info['selected_radio_id'] is None


def test_formation_forwarding_preserves_original_bytes_budget_and_age():
    relay=FormationRelays('head','tail');sent=[]
    for i in range(3):
        now=i*.1
        head=encode_beacon(Beacon('head',i,now,(50.,0.,0.,10.,0.,0.)))
        tail=encode_beacon(Beacon('tail',i,now,(0.,0.,0.,10.,0.,0.)))
        relay.add(head);relay.add(tail)
        raw=relay.take(now);assert raw in (head,tail)
        sent.append(decode_beacon(raw).vehicle_id)
        assert relay.take(now) is None
    assert sent==['head','head','tail']
    assert relay.take(1.) is None


def test_fresh_peer_chain_outlives_local_memory_without_becoming_fresh_control():
    from integrations.connected_v2v.autonomy.controller import Track,Scan,Detection
    node=V2VEndpoint('follower');c=SettlingFollower(node)
    c.tracks['track-1']=Track('track-1',0.,50.,0.,10.,0.,0,'track-1');c.selected='track-1'
    for i in range(31):
        now=i*.1;d=0. if now<=2 else min(3.5,(now-2)*3.5)
        angle=math.atan2(d,50.);rate=3.5*math.sin(angle) if 2<now<3 else 0.
        c.peer_scans['observer']=Scan(i,now,(10*now,0.,0.,10.,0.,0.),
            (Detection(math.hypot(50,d),angle,rate),),complete=False)
        evidence=c._peer_evidence('track-1',now)
        assert evidence and evidence[-1][4]==now
    assert c.tracks['track-1'].observed_s==0.
    assert c.cooperative_anchors['track-1'][4]==3.
    assert c._peer_evidence('track-1',3.3)==[]
    node.observe_local((0.,0.,0.,10.,0.,0.),3.3,3.3)
    cmd,info=c.decide(3.3)
    assert cmd.accel==-6. and info['sensor_source']=='none'


def test_speculative_lateral_motion_is_not_target_membership():
    from integrations.connected_v2v.autonomy.controller import Track
    node=V2VEndpoint('follower');c=SettlingFollower(node)
    assert not c._in_lane(50.,2.6,-5.,0.)
    assert lane_guard([(50.,2.6,10.,-5.)],0.,20.,True)[1][0]['relevant']
    track=Track('t',0.,50.,1.8,10.,-1.,0,'t')
    assert not c._radar_in_lane(track,50.,1.8,0.)
    assert not c._radar_in_lane(track,50.,1.8,0.)
    track=Track('t',.1,51.,1.8,10.,-1.,1,'t')
    assert c._radar_in_lane(track,51.,1.8,0.)


def test_established_following_needs_observed_cutin_and_distinct_sources():
    node=V2VEndpoint('ego-car');c=SettlingFollower(node)
    head,intruder=V2VEndpoint('head'),V2VEndpoint('intruder')
    reports=[]
    for t,d in [(0.,3.5),(.1,1.5),(.15,1.5),(.2,1.5),(.3,1.5),(.35,1.5)]:
        node.observe_local((0.,0.,0.,12.,0.,0.),t,t)
        if t in (0.,.1,.2,.3):
            node.receive(head.publish((80.,0.,0.,12.,0.,0.),t,t),t)
            node.receive(intruder.publish((50.,d,0.,12.,0.,0.),t,t),t)
        _,info=c.decide(t);reports.append(info)
    assert reports[0]['selection_event']=='acquired'
    assert reports[0]['confirmed_following_frames']==0
    assert reports[1]['selection_event']=='cut_in'
    assert reports[2]['confirmed_following_frames']==1
    assert all(z['lateral_guard_mode']=='conservative' for z in reports[:5])
    assert reports[-1]['confirmed_following_frames']==3
    assert reports[-1]['lateral_guard_mode']=='lane_aware'
    # A newly missing selected predecessor is not made available by this mode.
    node.observe_local((0.,0.,0.,12.,0.,0.),1.,1.)
    cmd,info=c.decide(1.)
    assert cmd.accel==-6 and info['sensor_source']=='none'


def test_native_maximum_stop_request_holds_and_release_tracks_actual_speed():
    from .native_vehicle import native_actuation
    stopped_goal=native_actuation(16.,14.,-6.,16.,0)
    assert stopped_goal==dict(setpoint_m_s=0.,brake_intensity=0.,emergency=True,
        mode='motor_stop',remaining_brake_ticks=6)
    held=native_actuation(0.,10.,2.5,16.,6)
    assert held['emergency'] and held['remaining_brake_ticks']==5
    assert held['brake_intensity']==0. and held['mode']=='motor_stop'
    released=native_actuation(0.,8.,2.,16.,1)
    assert released==dict(setpoint_m_s=8.1,brake_intensity=0.,emergency=False,
        mode='speed',remaining_brake_ticks=0)


def test_native_normal_deceleration_discards_positive_setpoint_windup():
    from .native_vehicle import native_actuation
    request=native_actuation(16.,10.,-2.,20.,0)
    assert request==dict(setpoint_m_s=9.9,brake_intensity=0.,emergency=False,
        mode='speed',remaining_brake_ticks=0)


def test_native_reserve_uses_the_slow_plant_before_nominal_guard():
    from .native_vehicle import native_braking_guard
    from integrations.unified_lans.physics import Command
    road=CircularRoad();state=(0.,0.,0.,14.,0.,0.)
    observation=dict(s=34.6,d=0.,speed=6.,lateral=0.,relevant=True)
    original=Command(0.,2.5)
    nominal,_=lane_guard([(34.6,0.,6.,0.)],0.,14.,False)
    assert not nominal
    protected,info=native_braking_guard(original,dict(guard_objects=[observation]),state,road)
    assert protected.accel==-6. and info['active']
    observation['relevant']=False
    assert native_braking_guard(original,dict(guard_objects=[observation]),state,road)[0]==original


def test_native_clipped_fov_edge_is_unavailable_not_a_center_or_clear_road():
    import numpy as np
    from .native_vehicle import adapt_scan
    profile=dict(miss=0.,burst=False)
    state=(0.,0.,0.,8.,0.,0.)
    edge=dict(distance=8.,azimuth=.349,speed=0.)
    scan=adapt_scan(1,.1,state,[edge],profile,np.random.default_rng(1))
    assert scan.detections==() and not scan.complete
    center=dict(distance=30.,azimuth=.1,speed=-2.)
    scan=adapt_scan(2,.2,state,[center],profile,np.random.default_rng(1))
    assert len(scan.detections)==1 and not scan.complete


def test_native_recovery_cap_preserves_catchup_inside_the_steering_envelope():
    from .native_vehicle import native_speed_cap,native_actuation
    assert native_speed_cap(12.,True)==16. and native_speed_cap(8.,True)==16.
    assert native_speed_cap(12.,False)==12.
    assert native_actuation(15.99,15.99,2.5,native_speed_cap(12.,True),0)['setpoint_m_s']==16.
