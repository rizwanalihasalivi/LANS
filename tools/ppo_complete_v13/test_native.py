"""Native bridge geometry and isolated-world contracts without opening holdouts."""
import json,math,runpy
from types import SimpleNamespace
import numpy as np
import pytest
from tools.unified_campaign.study import StudyRoute
from tools.unified_control_v9.native_adapter import Frame
from .native import ROOT,prepare_episode,sha
from .native_adapter import body_state,steering,make_controller


def fixture(scenario='crossing',mirror=-1):
    return dict(id=-301,stage='native_semantic_test_only',scenario=scenario,mirror=mirror,
        speed=12.,delay=.1,stiffness=.83,lateral=.21*mirror,heading=.008,phase=11.,amplitude=1.11,
        npc_x_shift=1.1,npc_speed_scale=.93,network='nominal',network_seed=1890)


@pytest.mark.parametrize('target',[-.49,-.2,-1e-6,0.,1e-6,.2,.49])
def test_ackermann_measurement_recovers_bicycle_angle(target):
    # Independent Driver steering geometry, including the native right-positive
    # sign convention. Averaging the two wheel angles would fail at large turns.
    if target:
        cot=1/math.tan(-target)
        right=math.atan(1/(cot-1.6/(2*2.6)))
        left=math.atan(1/(cot+1.6/(2*2.6)))
    else:left=right=0.
    measured=steering(SimpleNamespace(getValue=lambda:left),SimpleNamespace(getValue=lambda:right))
    assert measured==pytest.approx(target,abs=1e-12)


def test_body_pose_is_converted_to_cg_and_body_velocity_without_state_mutation():
    yaw=.7;c,s=math.cos(yaw),math.sin(yaw);position=[8.,-3.,.3]
    orientation=[c,-s,0.,s,c,0.,0.,0.,1.]
    # Input world velocity corresponds to forward12m/s, left.4m/s.
    velocity=[12*c-.4*s,12*s+.4*c,0.,0.,0.,.2]
    node=SimpleNamespace(getPosition=lambda:position,getOrientation=lambda:orientation,getVelocity=lambda:velocity)
    state=body_state(node)
    assert state==pytest.approx([8+1.4*c,-3+1.4*s,yaw,12.,.4,.2])
    assert position==[8.,-3.,.3] and orientation[0]==c


@pytest.mark.parametrize('kind',['straight','lane_change','sine'])
@pytest.mark.parametrize('mirror',[-1,1])
def test_rigid_map_initialization_and_traffic_inverse(kind,mirror):
    route=StudyRoute(kind,mirror,11.,1.11);initial=np.array([104.,3.,.002,12.,.1,.02])
    frame=Frame(initial,route,.21*mirror,.008);mapped=frame.transform(initial)
    y,h,_=route.geometry(0.)
    assert mapped==pytest.approx([0.,y+.21*mirror,h+.008,12.,.1,.02])
    target=np.array([31.,-20.*mirror]);world_cg=frame.origin+frame.rotation.T@(target-frame.offset)
    traffic=np.r_[world_cg,math.pi/2,8.,0.,0.]
    assert frame.transform(traffic)[:2]==pytest.approx(target,abs=1e-12)
    assert frame.metadata()['physical_pose_changed'] is False


@pytest.mark.parametrize('scenario',['following','merge','crossing','curved'])
def test_world_builder_keeps_physics_identical_across_matched_methods(tmp_path,monkeypatch,scenario):
    case=fixture(scenario);lqr,wl=prepare_episode(tmp_path/'lqr',case,'lqr')
    adaptive,wa=prepare_episode(tmp_path/'adaptive',case,'adaptive')
    assert wl.read_bytes()==wa.read_bytes()
    a=json.loads((lqr/'case.json').read_text());b=json.loads((adaptive/'case.json').read_text())
    assert a['initial_ego']==b['initial_ego'] and a['initial_npcs']==b['initial_npcs']
    assert a['npc_defs']==b['npc_defs'] and a['controller_kwargs']==b['controller_kwargs']
    world=wa.read_text();assert world.count('DEF VEHICLE Car {')==1
    assert world.count('controller "v13_npc"')==len(b['initial_npcs'])
    assert world.count('engineMaxPower 100000')==1+len(b['initial_npcs'])
    assert world.count('wheelsDampingConstant 0.2')==1+len(b['initial_npcs'])
    protocol=json.loads((adaptive/'protocol.json').read_text())
    assert sha(wa)==protocol['world_sha256']
    for name,digest in protocol['protos'].items():assert sha(adaptive/'project'/name)==digest
    # Starting a spawned policy process imports its entry as __mp_main__.
    # That import must never create a second Driver/controller connection.
    monkeypatch.setenv('LANS_ROOT',str(ROOT))
    entry=adaptive/'project/controllers/v13_native/v13_native.py'
    imported=runpy.run_path(str(entry),run_name='__mp_main__')
    assert 'driver' not in imported and 'Driver' not in imported
    # Physical stiffness belongs in the tire law, not controller initialization.
    first=make_controller(b,'adaptive');changed=dict(b,stiffness=1.24)
    second=make_controller(changed,'adaptive')
    assert first.stiffness_estimate==second.stiffness_estimate==1.
    assert first.stiffness_uncertainty==second.stiffness_uncertainty
