"""Read-only standard-library scoring check; imports no controller or plant code."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collision(a, b):
    tangents = [(math.cos(z[2]), math.sin(z[2])) for z in (a, b)]
    normals = [(-t[1], t[0]) for t in tangents]
    dot = lambda u,v: u[0]*v[0]+u[1]*v[1]
    delta = (b[0]-a[0], b[1]-a[1])
    for axis in tangents+normals:
        radius = sum(2.3*abs(dot(t, axis))+.9*abs(dot(n, axis)) for t,n in zip(tangents, normals))
        if abs(dot(delta, axis)) > radius:
            return False
    return True


def check_sources(root):
    plan = read(root/'plan.json')
    for name, expected in plan['sources'].items():
        assert sha(root/'source'/name) == expected, ('Snapshot mismatch', name)


def safety(command, info, now):
    bound = not (-6. <= command['accel'] <= 2.5 and abs(command['steering']) <= .5+1e-9)
    blind = info['selection_brake'] and command['accel'] != -6.
    stale = False
    if info['sensor_source'] in ('radar', 'v2v'):
        age = now-info['selected_observed_s']
        stale = not (-1e-9 <= age <= (.2 if info['sensor_source'] == 'radar' else .4)+1e-9)
    return int(bound), int(blind), int(stale)


def check_python(root):
    root = Path(root)
    check_sources(root)
    summary = read(root/'summary.json')
    total = 0
    for aggregate in summary['results']:
        path = root/f"{aggregate['case']}-{aggregate['seed']}"
        stored = read(path/'summary.json')
        case = read(path/'case.json')
        assert stored == aggregate
        assert sha(path/'ticks.jsonl') == stored['raw_sha256'] and sha(path/'case.json') == stored['case_sha256']
        data = rows(path/'ticks.jsonl')
        assert len(data) == round(case['seconds']/.05) == 400
        counts = dict(collisions=0, bound_violations=0, blind_brake_violations=0, stale_source_ticks=0, corridor_ticks=0)
        radius = case['road']['radius']
        project = lambda z: (radius*math.atan2(z[0], radius-z[1]), radius-math.hypot(z[0], radius-z[1])) if radius else (z[0], z[1])
        for i, row in enumerate(data):
            assert row['tick'] == i and row['time_s'] == i*.05
            counts['collisions'] += sum(collision(row['after'], z) for z in row['traffic_after'].values())
            b, blind, stale = safety(row['command'], row['decision'], row['time_s'])
            counts['bound_violations'] += b
            counts['blind_brake_violations'] += blind
            counts['stale_source_ticks'] += stale
            counts['corridor_ticks'] += abs(project(row['after'])[1]) > 1.75
        for key, value in counts.items():
            assert stored[key] == value == 0, (path.name, key, value)
        progress = project(data[-1]['after'])[0]-project(data[0]['before'])[0]
        assert math.isclose(progress, stored['progress_m'], abs_tol=1e-9) and progress > 25.
        assert stored['acquired_intruder_ticks'] > 0 and stored['recovered_leader_ticks'] > 0
        assert stored['passed'] and read(path/'replay.json')['passed']
        total += len(data)
    assert summary['passed'] and len(summary['results']) == 40
    return dict(passed=True, episodes=40, ego_ticks=total)


def check_native(root):
    root = Path(root)
    check_sources(root)
    summary = read(root/'summary.json')
    total = 0
    for aggregate in summary['results']:
        path = root/f"{aggregate['case']}-{aggregate['seed']}"
        assert read(path/'verification.json') == aggregate
        record = read(path/'provenance.json')
        assert sha(path/'project/worlds/autonomous.wbt') == record['world_sha256']
        assert sha(path/'project/controllers/autonomous_vehicle/autonomous_vehicle.py') == record['controller_sha256']
        traces = {name:rows(path/f'{name}.jsonl') for name in ('follower', 'leader', 'intruder')}
        assert all(len(data) == 600 for data in traces.values())
        counts = dict(collisions=0, bound_violations=0, blind_brake_violations=0, stale_source_ticks=0)
        for i, row in enumerate(traces['follower']):
            counts['collisions'] += sum(collision(row['state'], traces[name][i]['state']) for name in ('leader', 'intruder'))
            b, blind, stale = safety(row['command'], row['decision'], row['time_s'])
            counts['bound_violations'] += b
            counts['blind_brake_violations'] += blind
            counts['stale_source_ticks'] += stale
            for event in row['radio']:
                beacon = json.loads(event['message'])
                name = beacon['vehicle_id']
                source = traces[name][round(beacon['observed_s']/.05)-1]
                assert source['state'] == beacon['state'] and source['time_s'] == beacon['observed_s']
                assert row['time_s'] >= beacon['observed_s']
                assert not (record['case'] == 'nonconnected' and name == 'intruder')
        for key, value in counts.items():
            assert aggregate[key] == value == 0, (path.name, key, value)
        progress = traces['follower'][-1]['state'][0]-traces['follower'][0]['state'][0]
        assert aggregate['progress_m'] == progress and progress > 25.
        assert aggregate['acquired_intruder_ticks'] > 0 and aggregate['recovered_leader_ticks'] > 0
        assert aggregate['passed']
        total += 3*len(traces['follower'])
    assert summary['passed'] and len(summary['results']) == 12
    return dict(passed=True, episodes=12, native_samples=total)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True)
    parser.add_argument('--native', required=True)
    args = parser.parse_args()
    print(json.dumps(dict(python=check_python(args.python), native=check_native(args.native)), indent=2))


if __name__ == '__main__':
    main()
