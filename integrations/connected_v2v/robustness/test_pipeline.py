from dataclasses import replace
import itertools
import json
import numpy as np
import pytest
from integrations.connected_v2v.messages import Beacon,encode_beacon,decode_beacon
from integrations.connected_v2v.autonomy.study import overlaps
from .relay import PendingRelays
from .scenarios import PROFILES,Scene,radar_scan
from .study import run_episode,replay,digest
from .native import configuration
from .world import prepare
from integrations.connected_v2v.autonomy.road import Road


def test_forwarding_preserves_original_bytes_and_expires_without_refreshing_age():
    queue=PendingRelays()
    first=encode_beacon(Beacon('a',4,1.,(0.,0.,0.,12.,0.,0.)))
    second=encode_beacon(Beacon('b',8,1.,(20.,0.,0.,12.,0.,0.)))
    queue.add(first);queue.add(second)
    assert queue.take(1.1)==first
    assert queue.take(1.1)==second
    queue.add(first)
    assert queue.take(1.3) is None
    assert decode_beacon(first).observed_s==1.


def test_relay_budget_prioritizes_reference_lane_without_using_vehicle_roles():
    queue=PendingRelays()
    adjacent=encode_beacon(Beacon('a',0,0.,(20.,3.5,0.,12.,0.,0.)))
    inlane=encode_beacon(Beacon('z',0,0.,(70.,0.,0.,12.,0.,0.)))
    queue.add(adjacent);queue.add(inlane)
    assert queue.take(.1,Road())==inlane
    assert queue.take(.1,Road())==adjacent


def test_occluded_and_missed_targets_do_not_supply_a_clearance_or_identity_oracle():
    profile=replace(PROFILES['curved'],radius=0.,miss=0.,range_noise=0.,bearing_noise=0.,rate_noise=0.)
    ego=np.array([0.,0.,0.,12.,0.,0.])
    traffic={name:np.array([x,0.,0.,12.,0.,0.]) for name,x in [('near',20.),('hidden',40.)]}
    scan=radar_scan(0,0.,ego,traffic,profile,np.random.default_rng(1))
    assert len(scan.detections)==1 and scan.detections[0].distance_m==20.
    assert not scan.complete and not hasattr(scan.detections[0],'target_id')
    lost=radar_scan(1,.1,ego,traffic,replace(profile,miss=1.),np.random.default_rng(1))
    assert not lost.detections and not lost.complete


@pytest.mark.parametrize('case',['dense_curved','occlusion_brake','combined'])
def test_scripted_npc_fixture_keeps_its_own_headways_through_the_merge(case):
    for speed in (8.,12.,16.):
        scene=Scene(case,speed,701)
        for t in (0.,6.,18.,20.,22.,32.):
            assert not any(overlaps(a,b) for a,b in itertools.combinations(scene.states(t).values(),2))


def test_physical_native_curved_road_and_nonconnected_membership(tmp_path):
    config=configuration('dense_curved',8.,811)
    world=prepare(tmp_path/'native',config)
    text=world.read_text()
    assert 'boundingObject USE ROAD_MESH' in text and 'IndexedFaceSet' in text
    assert len(config['starts'])==8 and 'intruder' not in config['connected']
    assert text.count('Radar {')==8 and 'angularNoise' in text
    source=(tmp_path/'native/project/controllers/robust_vehicle/robust_vehicle.py').read_text()
    assert 'getFromDef' not in source and '.retarget(' not in source
    compile(source,'robust_vehicle.py','exec')


def test_relay_sensor_physics_replay_rejects_changed_aggregate(tmp_path):
    path=tmp_path/'run';run_episode(path,'curved',8.,701,seconds=.5)
    assert replay(path)['passed']
    summary=json.loads((path/'summary.json').read_text());summary['progress_m']+=1.
    (path/'summary.json').write_text(json.dumps(summary))
    with pytest.raises(AssertionError,match='Aggregate mismatch'):replay(path)
