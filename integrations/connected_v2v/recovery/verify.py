"""Rebuild receiver/control histories; independently aggregate scoring metrics."""
from dataclasses import asdict
import itertools
import json
import math
from pathlib import Path
import numpy as np
from integrations.connected_v2v.demo import digest
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.platoon import FollowingConfig
from integrations.unified_lans.physics import Command, advance
from integrations.unified_lans.physics import Config
from integrations.connected_v2v.messages import decode_beacon
from .controller import FusionFollower, RangeObservation, RADAR_TTL

NAMES = ('leader', 'follower-1', 'follower-2')


def summarize(rows, following):
    errors, jerk, gaps = [], [], []
    progress = {name:0. for name in NAMES[1:]}
    previous = {name:0. for name in NAMES[1:]}
    target = {'follower-1':'leader', 'follower-2':'follower-1'}
    collisions = corridor = stale = bounds = fallbacks = 0
    source_counts = {}
    for row in rows:
        now = row['time_s']; target.update(row['membership'])
        for a, b in itertools.combinations(row['after'].values(), 2):
            collisions += float(np.linalg.norm(np.array(a[:2])-b[:2])) <= 4.6
        for name in NAMES[1:]:
            state, front = row['after'][name], row['after'][target[name]]
            gap = front[0]-state[0]-4.6
            gaps.append(gap)
            errors.append((gap-following.standstill_gap_m-following.time_headway_s*state[3])**2)
            command, info = row['controls'][name]['command'], row['controls'][name]['decision']
            jerk.append(((command['accel']-previous[name])/.05)**2)
            previous[name] = command['accel']
            corridor += abs(state[1]) > 1.75
            bounds += not (-6. <= command['accel'] <= 2.5 and abs(command['steering']) <= .5+1e-9)
            source = info['sensor_source']; source_counts[source] = source_counts.get(source, 0)+1
            if source in ('radar', 'v2v'):
                age = now-info['selected_observed_s']
                stale += not (0 <= age <= (RADAR_TTL if source == 'radar' else .4)+1e-9)
            fallbacks += info['source'] in ('fallback_brake', 'hold_brake')
            progress[name] += state[0]-row['before'][name][0]
    return dict(spacing_rms_m=float(math.sqrt(sum(errors)/len(errors))),
                jerk_rms_m_s3=float(math.sqrt(sum(jerk)/len(jerk))),
                min_gap_m=float(min(gaps)), collision_pair_ticks=int(collisions),
                corridor_ticks=int(corridor), stale_source_ticks=int(stale), bound_violations=int(bounds),
                fallback_ticks=int(fallbacks), progress_m=progress, source_counts=source_counts,
                vehicle_ticks=3*len(rows))


def replay(path):
    path = Path(path)
    case = json.loads((path/'case.json').read_text())
    summary = json.loads((path/'summary.json').read_text())
    assert digest(path/'ticks.jsonl') == summary['raw_sha256']
    assert digest(path/'case.json') == summary['case_sha256']
    rows = [json.loads(line) for line in (path/'ticks.jsonl').read_text().splitlines()]
    following = FollowingConfig(**case['following'])
    assert case['config'] == asdict(Config())
    nodes = {name:V2VEndpoint(name) for name in NAMES}
    controls = {name:FusionFollower(nodes[name], NAMES[i-1] if i else None,
                                    method=case['method'], following=following) for i, name in enumerate(NAMES)}
    previous = None
    for tick, row in enumerate(rows):
        now = tick*.05
        assert row['tick'] == tick and row['time_s'] == now
        for name in NAMES:
            np.testing.assert_allclose(row['before'][name], previous[name] if previous else case['initial'][name], rtol=0, atol=1e-10)
        expected_membership = {}
        if case['scenario'] == 'cut_in':
            if tick == round((3.5+case['shift'])/.05):expected_membership={'follower-1':'cut-in'}
            if tick == round((12.5+case['shift'])/.05):expected_membership={'follower-1':'leader'}
        assert row['membership'] == expected_membership, 'Unscheduled membership change'
        for name, target in row['membership'].items():
            controls[name].retarget(target)
        for name, observation in row['local'].items():
            assert not (case['scenario']=='ego_blackout' and name=='follower-1' and 1.+case['shift']<=now<1.6+case['shift'])
            assert observation['observed_s'] == now
            nodes[name].observe_local(observation['state'], observation['observed_s'], now)
            # The sensor is ideal but local only; no missing-local sample may
            # be replaced with raw scoring state during replay.
            np.testing.assert_allclose(observation['state'], row['before'][name], rtol=0, atol=1e-10)
        for event in row['radio']:
            assert event['received_s'] == now
            beacon=decode_beacon(event['message'].encode())
            source=rows[round(beacon.observed_s/.05)]
            assert beacon.vehicle_id==event['sender'] and beacon.sequence==event['sequence']
            np.testing.assert_array_equal(beacon.state,source['before'][beacon.vehicle_id])
            if beacon.vehicle_id!='cut-in':assert beacon.vehicle_id in source['local']
            assert nodes[event['receiver']].receive(event['message'].encode(), now) == event['accepted']
        for event in row['radar']:
            obs = RangeObservation(**event['observation'])
            source=rows[round(obs.observed_s/.05)]
            own=source['local'][event['receiver']]['state'];front=source['before'][obs.target_id]
            np.testing.assert_array_equal(obs.ego_state,own)
            assert abs(obs.gap_m-max(0.,min(120.,front[0]-own[0]-4.6)))<=.10000001
            assert abs(obs.relative_speed_m_s-(front[3]-own[3]))<=.05000001
            assert not (case['scenario'] in ('radar_blackout','dual_blackout') and event['receiver']=='follower-1' and 1.+case['shift']<=obs.observed_s<2.5+case['shift'])
            assert controls[event['receiver']].observe_radar(obs, now) == event['accepted']
        for name in NAMES:
            scheduled = -3. if case['scenario'] == 'leader_brake' and 2.+case['shift'] <= now < 3.+case['shift'] else None
            command, decision = controls[name].decide(now, leader_accel=scheduled if name == 'leader' else None)
            stored = row['controls'][name]
            assert asdict(command) == stored['command'] and decision == stored['decision'], 'Decision replay mismatch'
            np.testing.assert_allclose(advance(row['before'][name], command, .05), row['after'][name],
                                       rtol=0, atol=1e-10, err_msg='Physics replay mismatch')
        if 'cut-in' in row['before']:
            npc = np.array(row['before']['cut-in'])
            if previous is not None and 'cut-in' in previous:
                np.testing.assert_allclose(npc, previous['cut-in'], rtol=0, atol=1e-10)
            else:
                assert case['scenario'] == 'cut_in' and math.isclose(now, 3.+case['shift'], abs_tol=1e-9)
                assert npc[0] == (row['before']['leader'][0]+row['before']['follower-1'][0])/2
            npc[0] += npc[3]*.05
            t = now+.05-case['shift']
            npc[1] = 3.5*max(0.,1-(t-3.)) if t < 4. else (0. if t < 12. else min(7.,3.5*(t-12.)))
            np.testing.assert_allclose(npc, row['after']['cut-in'], rtol=0, atol=1e-10)
        previous = row['after']
    assert len(rows) == round(case['seconds']/.05), 'Incomplete episode'
    metrics = summarize(rows, following)
    assert all(metrics[key] == summary[key] for key in metrics), 'Aggregate mismatch'
    return dict(passed=True, ticks=3*len(rows), receiver_control_replay=True,
                physics='shared bicycle replay, not independent model validation')
