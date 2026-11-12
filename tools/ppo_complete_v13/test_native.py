"""Native bridge geometry and isolated-world contracts without opening holdouts."""
import hashlib,json,math,re,runpy
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


def synthetic_scene(tmp_path,case):
    """Semantic measured-displacement fixture, not actual native evidence."""
    calibration,_=prepare_episode(tmp_path/'scene',case,'lqr',warmup_only=True)
    data=json.loads((calibration/'case.json').read_text())
    # Translation invariance is checked using arbitrary finite warmup drift,
    # not a copy of the implementation's map transform or ideal NPC integrator.
    ego=np.array([111.3,-.17,.003,11.98,-.00002,.000001]);npcs={}
    _,h,_=StudyRoute(data['route_kind'],case['mirror'],case['phase'],case['amplitude']).geometry(0.)
    for i,(name,state) in enumerate(data['initial_npcs'].items()):
        angle=state[2]-h-case['heading'];old=np.array([-100.-20*i,100.+30*i])
        displacement=np.array([math.cos(angle),math.sin(angle)])*state[3]*10+np.array([.013,-.027])
        cg=old+displacement+1.4*np.array([math.cos(angle+.00001),math.sin(angle+.00001)])
        npcs[name]=[*cg,angle+.00001,state[3]-.012,0.000003,.000001]
    scene=dict(warmup_only=True,fixture_sha256=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
        ego_native=ego.tolist(),npc_native=npcs)
    (calibration/'scene-state.json').write_text(json.dumps(scene))
    return calibration,scene,data


@pytest.mark.parametrize('scenario',['following','merge','crossing','curved'])
@pytest.mark.parametrize('mirror',[-1,1])
def test_measured_scene_sets_initial_world_positions_for_correct_warm_end_scene(tmp_path,scenario,mirror):
    case=fixture(scenario,mirror);calibration,scene,base=synthetic_scene(tmp_path,case)
    lqr,wl=prepare_episode(tmp_path/'lqr',case,'lqr',scene_calibration=calibration,warmup_only=False)
    adaptive,wa=prepare_episode(tmp_path/'adaptive',case,'adaptive',scene_calibration=calibration,warmup_only=False)
    # Same policy-free scene and physical world for both matched controllers.
    assert wl.read_bytes()==wa.read_bytes()
    a=json.loads((lqr/'case.json').read_text());b=json.loads((adaptive/'case.json').read_text())
    assert not a['warmup_only'] and not b['warmup_only']
    assert a['scene_calibration']==b['scene_calibration']==str(calibration)
    for out in (lqr,adaptive):
        protocol=json.loads((out/'protocol.json').read_text())
        assert protocol['scene_calibration_sha256']==sha(calibration/'scene-state.json')
        assert protocol['physical_initialization'].endswith('no pose/velocity/force writes')
    route=StudyRoute(base['route_kind'],mirror,case['phase'],case['amplitude']);y,h,_=route.geometry(0.)
    alpha=h+case['heading']-scene['ego_native'][2];cosine,sine=math.cos(alpha),math.sin(alpha)
    origin=np.asarray(scene['ego_native'][:2]);world=wa.read_text()
    for i,(name,state) in enumerate(base['initial_npcs'].items()):
        match=re.search(r'DEF '+re.escape(base['npc_defs'][name])+r' Car \{\s*translation ([^\n]+)\n\s*rotation ([^\n]+)',world)
        assert match is not None
        translation=np.array([float(v) for v in match.group(1).split()]);rotation=[float(v) for v in match.group(2).split()]
        assert translation[2]==.36 and rotation[:3]==[0.,0.,1.]
        assert rotation[3]==pytest.approx(state[2]-h-case['heading'])
        # A homogeneous plane preserves measured warmup displacement when the
        # initial car translation changes. Apply that displacement independently,
        # then rotate into the ego map and require the exact requested NPC point.
        old_spawn=np.array([-100.-20*i,100.+30*i])
        world_warm_end=translation[:2]+np.asarray(scene['npc_native'][name][:2])-old_spawn
        delta=world_warm_end-origin
        map_warm_end=np.array([cosine*delta[0]-sine*delta[1],sine*delta[0]+cosine*delta[1]+y+case['lateral']])
        assert map_warm_end==pytest.approx(state[:2],abs=1e-11)


def test_scene_calibration_rejects_fixture_mismatch_and_non_calibration_input(tmp_path):
    case=fixture();calibration,scene,_=synthetic_scene(tmp_path,case)
    with pytest.raises(AssertionError):
        prepare_episode(tmp_path/'wrong-fixture',dict(case,mirror=1),'adaptive',scene_calibration=calibration)
    scene['warmup_only']=False;(calibration/'scene-state.json').write_text(json.dumps(scene))
    with pytest.raises(AssertionError):
        prepare_episode(tmp_path/'not-calibration',case,'adaptive',scene_calibration=calibration)
