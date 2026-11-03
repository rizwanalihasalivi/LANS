"""Fresh native cut-in/out development evidence; no final thesis comparison."""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import numpy as np
from integrations.connected_v2v.node import V2VEndpoint
from .controller import AutonomousFollower, Detection
from .study import ROOT, decode_scan, digest, overlaps, source_files, write

CASES = ('connected', 'nonconnected', 'v2v_blackout', 'dual_blackout')
SEEDS = (42, 73, 109)


def prepare(output, seed):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output/'project'
    controller = project/'controllers/autonomous_vehicle'
    controller.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name('native_vehicle.py'), controller/'autonomous_vehicle.py')
    original = (ROOT/'integrations/webots/worlds/vehicle_validation.wbt').read_text()
    world, car = original.split('DEF VEHICLE Car {', 1)
    world = world.replace('../.runtime/protos/', str(ROOT/'integrations/webots/.runtime/protos')+'/')
    world = world.replace('translation 50 0 -0.1', 'translation 500 0 -0.1').replace('size 200 100 0.2', 'size 2000 100 0.2')
    world = world.replace('randomSeed 42', f'randomSeed {seed}')
    car = 'Car {'+car
    car = car.replace('controller "vehicle_validation"', 'controller "autonomous_vehicle"')
    car = car.replace('extensionSlot [', '''extensionSlot [
    GPS { name "local_gps" translation 1.4 0 0.4 }
    InertialUnit { name "local_imu" }
    Gyro { name "local_gyro" }
    Emitter { name "local_tx" channel 7 range 150 }
    Receiver { name "local_rx" channel 7 }
    Radar { name "local_radar" translation 1.4 0 0.4 minRange 0.5 maxRange 120 horizontalFieldOfView 0.7 verticalFieldOfView 0.4 minRadialSpeed 0 maxRadialSpeed 0 rangeNoise 0.05 speedNoise 0.02 occlusion TRUE }''')
    rng = np.random.default_rng(seed)
    for name, x, y in [('leader', 70., 0.), ('follower', 0., 0.), ('intruder', 35.+float(rng.uniform(-1., 1.)), 3.5)]:
        instance = car.replace('translation 0 0 0.36', f'translation {x} {y} 0.36', 1)
        instance = instance.replace('name "lans-validation-surrogate"', f'name "{name}"\n  controllerArgs [ "{name}" ]')
        world += '\n'+instance
    (project/'worlds').mkdir()
    target = project/'worlds/autonomous.wbt'
    target.write_text(world)
    return target


def verify(output):
    output = Path(output)
    record = json.loads((output/'provenance.json').read_text())
    assert digest(output/'project/worlds/autonomous.wbt') == record['world_sha256']
    assert digest(output/'project/controllers/autonomous_vehicle/autonomous_vehicle.py') == record['controller_sha256']
    traces = {name:[json.loads(s) for s in (output/f'{name}.jsonl').read_text().splitlines()]
              for name in ('leader', 'follower', 'intruder')}
    node = V2VEndpoint('follower')
    control = AutonomousFollower(node, speed=8.)
    stale = bounds = blind = collisions = acquired = recovered = receipts = radar_frames = 0
    setpoint = 0.
    events = {}
    for name, rows in traces.items():
        assert len(rows) == json.loads((output/f'{name}-done.json').read_text())['samples'] == 600
        for i, row in enumerate(rows):
            assert row['sample'] == i and math.isclose(row['time_s'], (i+1)*.05, abs_tol=1e-8)
            position, rpy = row['native_pose']['position'], row['native_pose']['rpy']
            assert all(math.isfinite(v) for v in [*position, *rpy])
            assert -495. <= position[0] <= 1495. and abs(position[1]) < 5.
            assert .1 <= position[2] <= 2. and abs(rpy[0]) <= .35 and abs(rpy[1]) <= .35
            assert abs(rpy[2]) <= (.2 if name != 'intruder' else .6)
    for i, row in enumerate(traces['follower']):
        now = row['time_s']
        node.observe_local(row['state'], now, now)
        for event in row['radio']:
            assert node.receive(event['message'].encode(), now) == event['accepted']
            receipts += 1
        if row['scan'] is not None:
            scan = decode_scan(row['scan'])
            assert scan.observed_s == now and tuple(scan.ego_state) == tuple(row['state'])
            expected, complete = [], True
            for t in row['radar_targets']:
                if any(v is None or not math.isfinite(v) for v in t.values()):
                    complete = False
                    continue
                if .5 < t['distance'] < 119.8 and abs(t['azimuth']) <= .35:
                    try:
                        expected.append(Detection(t['distance']+.1, -t['azimuth'], t['speed']))
                    except ValueError:
                        complete = False
            assert scan.detections == tuple(expected) and scan.complete == complete, 'Native radar adapter mismatch'
            assert control.observe_scan(scan, now) == row['scan_accepted']
            radar_frames += 1
        command, info = control.decide(now)
        assert asdict(command) == row['command'] and info == row['decision'], 'Native decision replay mismatch'
        setpoint = max(0., min(16., setpoint+command.accel*.05))
        assert math.isclose(setpoint, row['setpoint_m_s'], abs_tol=1e-10)
        bounds += not (-6. <= command.accel <= 2.5 and abs(command.steering) <= .5+1e-9)
        blind += info['selection_brake'] and command.accel != -6.
        if info['sensor_source'] in ('radar', 'v2v'):
            stale += not (0 <= now-info['selected_observed_s'] <= (.2 if info['sensor_source'] == 'radar' else .4)+1e-9)
        events[info['selection_event']] = events.get(info['selection_event'], 0)+1
        state = row['state']
        for other in ('leader', 'intruder'):
            collisions += overlaps(state, traces[other][i]['state'])
        target = 'intruder' if 10. <= now < 14. else 'leader' if 23. <= now else None
        if target and info['target_gap_m'] is not None and not info['selection_brake']:
            gap = traces[target][i]['state'][0]-state[0]-4.6
            if abs(gap-info['target_gap_m']) < 2.:
                acquired += target == 'intruder'
                recovered += target == 'leader'
    progress = traces['follower'][-1]['state'][0]-traces['follower'][0]['state'][0]
    return dict(passed=not any((collisions, bounds, stale, blind)) and progress > 25. and acquired > 0 and recovered > 0,
                case=record['case'], seed=record['seed'], native_samples=1800, radio_receipts=receipts, radar_frames=radar_frames,
                collisions=int(collisions), bound_violations=int(bounds), stale_source_ticks=int(stale),
                blind_brake_violations=int(blind), progress_m=progress, acquired_intruder_ticks=acquired,
                recovered_leader_ticks=recovered, events=events,
                scope='native two-lane maneuver, three Cars; no physical safety or timing guarantee')


def run_one(output, case, seed):
    output = Path(output).resolve()
    world = prepare(output, seed)
    write(output/'provenance.json', dict(case=case, seed=seed, seconds=30.,
        world_sha256=digest(world), controller_sha256=digest(output/'project/controllers/autonomous_vehicle/autonomous_vehicle.py')))
    env = os.environ.copy()
    env.update(LANS_V2V_REPO=str(ROOT), LANS_AUTONOMY_NATIVE_OUTPUT=str(output), LANS_AUTONOMY_NATIVE_CASE=case,
               PATH='/workspace/lans-venv/bin:'+env.get('PATH', ''), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    with (output/'console.log').open('x') as log:
        subprocess.run(['bash', str(ROOT/'integrations/webots/run-webots.sh'), '--batch', '--mode=fast',
                        '--no-rendering', '--stdout', '--stderr', str(world)], cwd=ROOT, env=env,
                       stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
    result = verify(output)
    write(output/'verification.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    study = Path(args.study)
    assert json.loads((study/'summary.json').read_text())['passed'], 'Python development checks failed'
    plan = json.loads((study/'plan.json').read_text())
    for name, expected in plan['sources'].items():
        # Python episodes do not import native adapters or tests. Those have
        # their own source freeze below; every Python runtime dependency stays pinned.
        if Path(name).name in ('native.py', 'native_vehicle.py') or Path(name).name.startswith('test_'):
            continue
        assert digest(ROOT/name) == expected, ('Python source changed', name)
    runtime = ROOT/'integrations/webots/.runtime'
    subprocess.run(['sha256sum', '-c', '../runtime-sha256.txt'], cwd=runtime, check=True)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in source_files()}
    write(output/'plan.json', dict(cases=CASES, seeds=SEEDS, seconds=30., sources=hashes,
        python_plan_sha256=digest(study/'plan.json'), python_summary_sha256=digest(study/'summary.json')))
    for name in hashes:
        target = output/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    results = []
    for case in CASES:
        for seed in SEEDS:
            result = run_one(output/f'{case}-{seed}', case, seed)
            results.append(result)
            print(json.dumps(result), flush=True)
    write(output/'summary.json', dict(passed=all(r['passed'] for r in results), results=results))


if __name__ == '__main__':
    main()
