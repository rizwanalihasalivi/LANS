"""Development-only scenarios; truth generates inputs and scores, never selects targets."""
import argparse
from dataclasses import asdict
import hashlib
import heapq
import json
import math
from pathlib import Path
import platform
import shutil
import numpy as np
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.messages import decode_beacon
from integrations.connected_v2v.network import Link, SimulatedChannel
from integrations.unified_lans.physics import advance
from integrations.unified_lans.traffic import velocity
from .controller import AutonomousFollower, Detection, Scan
from .road import Road

ROOT = Path(__file__).resolve().parents[3]
CASES = ('connected', 'nonconnected', 'curved', 'dense', 'v2v_blackout',
         'dual_blackout', 'loss_jitter', 'delayed_radar')
SEEDS = (101, 203, 307, 409, 503)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def decode_scan(data):
    return Scan(data['sequence'], data['observed_s'], tuple(data['ego_state']),
                tuple(Detection(**d) for d in data['detections']), data['complete'])


def npc_states(road, now, parameters, dense=False):
    lateral = 3.5 if now < 3. else max(0., 3.5*(4.-now)) if now < 4. else (
              0. if now < 12. else min(3.5, 3.5*(now-12.)))
    dl = -3.5 if 3. <= now < 4. else 3.5 if 12. <= now < 13. else 0.
    traffic = [('leader', parameters['leader_s']+12.*now, 0., 12., 0.),
               ('intruder', parameters['intruder_s']+10.5*now, lateral, 10.5, dl)]
    if dense:
        traffic += [(f'adjacent-{i}', offset+12.*now, 3.5, 12., 0.)
                    for i, offset in enumerate((-40., -15., 70., 100., 140.))]
    result = {}
    for name, s, d, speed, lateral_speed in traffic:
        position = road.position(s, d)
        heading = s/road.radius if road.radius else 0.
        # s is arclength at the lane centre; actual tangential velocity includes
        # the offset-circle radius. All quantities are SI in world coordinates.
        tangential = speed*(1-d/road.radius) if road.radius else speed
        result[name] = np.array([*position, heading, tangential, lateral_speed,
                                 speed/road.radius if road.radius else 0.])
    return result


def sensor_scan(sequence, now, ego, traffic, rng):
    returns = []
    for state in traffic.values():
        delta = state[:2]-ego[:2]
        distance = float(np.linalg.norm(delta))
        bearing = math.atan2(delta[1], delta[0])-ego[2]
        bearing = math.atan2(math.sin(bearing), math.cos(bearing))
        if not .5 < distance < 119.9 or abs(bearing) > .34:
            continue
        rate = float((velocity(state)-velocity(ego))@(delta/distance))
        returns.append(Detection(distance+float(rng.uniform(-.05, .05)),
                                 bearing+float(rng.uniform(-.0003, .0003)),
                                 rate+float(rng.uniform(-.02, .02))))
    rng.shuffle(returns)  # Return order conveys no identity.
    return Scan(sequence, now, tuple(ego), tuple(returns))


def overlaps(a, b):
    """Oriented 4.6 x 1.8 m boxes, independent of following-controller IDs."""
    axes = [np.array([math.cos(z[2]), math.sin(z[2])]) for z in (a, b)]
    normals = [np.array([-axis[1], axis[0]]) for axis in axes]
    delta = np.array(b[:2])-a[:2]
    for axis in (*axes, *normals):
        radii = [2.3*abs(float(axes[i]@axis))+.9*abs(float(normals[i]@axis)) for i in (0, 1)]
        if abs(float(delta@axis)) > sum(radii):
            return False
    return True


def summarize(rows, road):
    collisions = bounds = stale = blind = corridor = 0
    acquisition = returns = 0
    events = {}
    for row in rows:
        ego = row['after']
        now = row['time_s']
        command, info = row['command'], row['decision']
        collisions += sum(overlaps(ego, other) for other in row['traffic_after'].values())
        bounds += not (-6. <= command['accel'] <= 2.5 and abs(command['steering']) <= .5+1e-9)
        corridor += abs(road.project(ego[:2])[1]) > 1.75
        blind += info['selection_brake'] and command['accel'] != -6.
        if info['sensor_source'] in ('radar', 'v2v'):
            age = now-info['selected_observed_s']
            stale += not (-1e-9 <= age <= (.2 if info['sensor_source'] == 'radar' else .4)+1e-9)
        event = info['selection_event']
        events[event] = events.get(event, 0)+1
        # Truth labels are used ONLY here, after control has been recorded.
        target = 'intruder' if 5. <= now < 10. else 'leader' if 15. <= now else None
        if target and info['target_gap_m'] is not None and not info['selection_brake']:
            gap = road.project(row['traffic_before'][target][:2])[0]-road.project(row['before'][:2])[0]-4.6
            if abs(gap-info['target_gap_m']) < 2.:
                acquisition += target == 'intruder'
                returns += target == 'leader'
    progress = road.project(rows[-1]['after'][:2])[0]-road.project(rows[0]['before'][:2])[0]
    passed = not any((collisions, bounds, stale, blind, corridor)) and progress > 25. and acquisition > 0 and returns > 0
    return dict(passed=bool(passed), ticks=len(rows), collisions=int(collisions), bound_violations=int(bounds),
                stale_source_ticks=int(stale), blind_brake_violations=int(blind), corridor_ticks=int(corridor),
                progress_m=progress, acquired_intruder_ticks=acquisition, recovered_leader_ticks=returns, events=events)


def run_episode(output, case, seed, *, seconds=20.):
    if case not in CASES or seconds <= 0 or abs(seconds/.05-round(seconds/.05)) > 1e-8:
        raise ValueError('known case and complete positive ticks required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    road = Road(500. if case == 'curved' else 0.)
    parameters = dict(leader_s=50.+float(rng.uniform(-1., 1.)),
                      intruder_s=25.+float(rng.uniform(-1., 1.)))
    ego = np.array([0., 0., 0., 12., 0., 0.])
    node = V2VEndpoint('follower')
    control = AutonomousFollower(node, road=road)
    traffic = npc_states(road, 0., parameters, case == 'dense')
    senders = {name:V2VEndpoint(name) for name in traffic if not (case == 'nonconnected' and name == 'intruder')}
    link = Link(delay_s=.05, jitter_s=.12, loss=.3, duplicate=.2) if case == 'loss_jitter' else Link(delay_s=.05)
    if case in ('v2v_blackout', 'dual_blackout'):
        link = Link(delay_s=.05, blackout=((5., 6.5),))
    channel = SimulatedChannel(seed, default=link)
    case_data = dict(case=case, seed=seed, seconds=seconds, road=asdict(road), parameters=parameters,
                     initial=ego.tolist(), connected=sorted(senders))
    write(output/'case.json', case_data)
    queue, rows = [], []
    for tick in range(round(seconds/.05)):
        now = tick*.05
        traffic = npc_states(road, now, parameters, case == 'dense')
        node.observe_local(ego, now, now)
        if tick % 2 == 0:
            for name, sender in senders.items():
                payload = sender.publish(traffic[name], now, now)
                channel.transmit(name, 'follower', payload, now, distance_m=float(np.linalg.norm(traffic[name][:2]-ego[:2])))
            if not (case == 'dual_blackout' and 5. <= now < 6.5):
                scan = sensor_scan(tick//2, now, ego, traffic, rng)
                heapq.heappush(queue, (now+(.15 if case == 'delayed_radar' else .05), scan.sequence, scan))
        radio_events = channel.deliver(now, {'follower':node})
        radar_events = []
        while queue and queue[0][0] <= now+1e-9:
            _, _, scan = heapq.heappop(queue)
            radar_events.append(dict(scan=asdict(scan), accepted=control.observe_scan(scan, now)))
        command, info = control.decide(now)
        after = advance(ego, command, .05)
        rows.append(dict(tick=tick, time_s=now, before=ego.tolist(), after=after.tolist(),
                         traffic_before={k:v.tolist() for k,v in traffic.items()},
                         traffic_after={k:v.tolist() for k,v in npc_states(road, now+.05, parameters, case == 'dense').items()},
                         radio=radio_events, radar=radar_events, command=asdict(command), decision=info))
        ego = after
    raw = output/'ticks.jsonl'
    raw.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))
    summary = summarize(rows, road)
    summary.update(case=case, seed=seed, raw_sha256=digest(raw), case_sha256=digest(output/'case.json'))
    write(output/'summary.json', summary)
    write(output/'replay.json', replay(output))
    return summary


def replay(output):
    output = Path(output)
    case = json.loads((output/'case.json').read_text())
    summary = json.loads((output/'summary.json').read_text())
    assert digest(output/'case.json') == summary['case_sha256']
    assert digest(output/'ticks.jsonl') == summary['raw_sha256']
    rows = [json.loads(line) for line in (output/'ticks.jsonl').read_text().splitlines()]
    assert len(rows) == round(case['seconds']/.05), 'Incomplete run'
    road = Road(**case['road'])
    node = V2VEndpoint('follower')
    control = AutonomousFollower(node, road=road)
    before = case['initial']
    rng = np.random.default_rng(case['seed'])
    expected_parameters = dict(leader_s=50.+float(rng.uniform(-1., 1.)),
                               intruder_s=25.+float(rng.uniform(-1., 1.)))
    assert expected_parameters == case['parameters']
    scans = {}
    for tick, row in enumerate(rows):
        now = tick*.05
        assert row['tick'] == tick and row['time_s'] == now
        np.testing.assert_allclose(row['before'], before, rtol=0, atol=1e-10, err_msg='State continuity mismatch')
        node.observe_local(row['before'], now, now)
        if tick % 2 == 0 and not (case['case'] == 'dual_blackout' and 5. <= now < 6.5):
            truth = npc_states(road, now, case['parameters'], case['case'] == 'dense')
            scans[tick//2] = sensor_scan(tick//2, now, np.array(row['before']), truth, rng)
        for event in row['radio']:
            assert event['received_s'] == now
            beacon = decode_beacon(event['message'].encode())
            assert beacon.vehicle_id in case['connected'] and beacon.sequence == round(beacon.observed_s/.1)
            truth = npc_states(road, beacon.observed_s, case['parameters'], case['case'] == 'dense')
            np.testing.assert_array_equal(beacon.state, truth[beacon.vehicle_id])
            assert node.receive(event['message'].encode(), now) == event['accepted']
        for event in row['radar']:
            scan = decode_scan(event['scan'])
            assert scan == scans.pop(scan.sequence), 'Sensor input mismatch'
            assert math.isclose(now-scan.observed_s, .15 if case['case'] == 'delayed_radar' else .05, abs_tol=1e-8)
            assert control.observe_scan(scan, now) == event['accepted']
        assert all(now-scan.observed_s < (.15 if case['case'] == 'delayed_radar' else .05)-1e-9
                   for scan in scans.values()), 'Missing sensor delivery'
        command, info = control.decide(now)
        assert asdict(command) == row['command'] and info == row['decision'], 'Decision replay mismatch'
        np.testing.assert_allclose(advance(row['before'], command, .05), row['after'], rtol=0, atol=1e-10,
                                   err_msg='Physics replay mismatch')
        for key, stamp in [('traffic_before', now), ('traffic_after', now+.05)]:
            expected = npc_states(road, stamp, case['parameters'], case['case'] == 'dense')
            assert set(expected) == set(row[key])
            for name in expected:
                np.testing.assert_array_equal(expected[name], row[key][name])
        before = row['after']
    metrics = summarize(rows, road)
    assert all(summary[key] == value for key, value in metrics.items()), 'Aggregate mismatch'
    return dict(passed=True, ticks=len(rows), receiver_control_replay=True, shared_bicycle_replay=True,
                scope='development only; shared replay is not independent dynamics validation')


def source_files():
    return sorted({*Path(__file__).parent.glob('*.py'),
                   *(ROOT/'integrations/connected_v2v').glob('*.py'),
                   ROOT/'integrations/connected_v2v/formation/controller.py',
                   ROOT/'integrations/connected_v2v/recovery/controller.py',
                   ROOT/'integrations/unified_lans/physics.py', ROOT/'integrations/unified_lans/traffic.py',
                   ROOT/'controllers/lqr_controller.py', ROOT/'models/bicycle_model.py'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in source_files()}
    write(output/'plan.json', dict(cases=CASES, seeds=SEEDS, seconds=20., sources=hashes,
                                 python=platform.python_version(), numpy=np.__version__,
                                 scope='development; final thesis benchmarking remains on hold'))
    for name in hashes:
        destination = output/'source'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    shutil.copyfile(Path(__file__).with_name('PROTOCOL.md'), output/'PROTOCOL.md')
    results = []
    for case in CASES:
        for seed in SEEDS:
            result = run_episode(output/f'{case}-{seed}', case, seed)
            results.append(result)
            print(json.dumps(result), flush=True)
    write(output/'summary.json', dict(passed=all(r['passed'] for r in results), results=results))
    manifest = {str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    write(output/'manifest.json', manifest)


if __name__ == '__main__':
    main()
