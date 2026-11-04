"""Staged native physical-road validation; every run retains its raw inputs."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,replace
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import traceback
import zlib
import numpy as np
from integrations.connected_v2v.autonomy.study import ROOT,digest,write,decode_scan
from .geometry import CircularRoad as Road
from integrations.connected_v2v.autonomy.native_vehicle import local_state
from integrations.connected_v2v.messages import decode_beacon
from integrations.connected_v2v.node import V2VEndpoint
from .controller import SettlingFollower
from .scenarios import PROFILES,NATIVE_CASES
from .native_vehicle import adapt_scan,native_actuation,native_braking_guard,native_speed_cap
from .world import prepare
from .metrics import measure
from .study import freeze,runtime_files,verify_sources
from .pacing import pace_goal
from integrations.connected_v2v.robustness.perception import is_peer_scan,decode_peer_scan

DEV_SEEDS=(6203,8011,12037)
VALIDATION_SEEDS=(16001,16007,16033,16057,16061)
DEV_SPEEDS=(8.,12.)


def configuration(case,speed,seed):
    p=PROFILES['noisy_nonconnected'] if case=='unreachable' else PROFILES[case]
    if p.radius:p=replace(p,radius=600.)
    rng=np.random.default_rng(np.random.SeedSequence([seed,7]))
    starts={'leader':(70.+float(rng.uniform(-2.,2.)),0.),'follower':(0.,0.),
            'intruder':(45.+float(rng.uniform(-2.,2.)),3.5)}
    if p.dense:starts.update({f'adjacent-{i}':(x,3.5) for i,x in enumerate((-70.,-40.,65.,95.,125.))})
    connected=[n for n in starts if not(p.nonconnected and n in ('intruder','adjacent-0','adjacent-2','adjacent-4'))]
    if case=='unreachable':
        starts={'leader':(260.,0.),'follower':(0.,0.),'intruder':(300.,3.5)}
        connected=['leader','follower']
    return dict(case=case,speed=speed,seed=seed,profile=asdict(p),starts=starts,connected=connected,seconds=70.)


def verify(output):
    output=Path(output);spec=json.loads((output/'config.json').read_text());road=Road(spec['profile']['radius'])
    record=json.loads((output/'provenance.json').read_text())
    assert digest(output/'project/worlds/robust.wbt')==record['world_sha256']
    assert digest(output/'project/controllers/robust_vehicle/robust_vehicle.py')==record['controller_sha256']
    traces={n:[json.loads(s) for s in (output/f'{n}.jsonl').read_text().splitlines()] for n in spec['starts']}
    for name,data in traces.items():
        assert len(data)==json.loads((output/f'{name}-done.json').read_text())['samples']==1400
        sensing_rng=np.random.default_rng(np.random.SeedSequence([spec['seed'],11,zlib.crc32(name.encode())]))
        setpoint=0.;brake_ticks=0
        for i,row in enumerate(data):
            assert row['sample']==i and math.isclose(row['time_s'],(i+1)*.05,abs_tol=1e-8)
            position=row['pose']['position'];rpy=row['pose']['rpy']
            assert all(math.isfinite(v) for v in [*position,*rpy])
            s,d,heading=road.project(position[:2])
            assert -140.<s<1500. and -1.75<d<5.25,('Road envelope',name,i,s,d)
            assert .1<position[2]<2. and abs(rpy[0])<.35 and abs(rpy[1])<.35,('Invalid pose',name,i)
            error=math.atan2(math.sin(rpy[2]-heading),math.cos(rpy[2]-heading))
            assert abs(error)<(.6 if name=='intruder' else .3),('Heading envelope',name,i,error)
            assert local_state(position,rpy[2],row['gps_velocity'],row['yaw_rate'])==row['state']
            cap=native_speed_cap(spec['speed'],name=='follower')
            assert row['native_speed_cap_m_s']==cap
            assert math.hypot(row['state'][3],row['state'][4])<=cap+.5,'Native validated speed envelope exceeded'
            actuator=native_actuation(setpoint,row['state'][3],row['command']['accel'],cap,brake_ticks)
            assert row['actuation']==actuator,'Native actuator replay mismatch'
            setpoint=actuator['setpoint_m_s'];brake_ticks=actuator['remaining_brake_ticks']
            assert math.isclose(setpoint,row['setpoint_m_s'],abs_tol=1e-10)
            assert row['applied_brake_intensity']==actuator['brake_intensity']
            assert row['applied_control_mode']==0
            assert math.isclose(row['applied_cruise_m_s'],setpoint,abs_tol=1e-10) and row['applied_throttle'] is None
            if row['generated_scan'] is not None:
                scan=adapt_scan((i+1)//2-1,row['time_s'],row['state'],row['radar_targets'],spec['profile'],sensing_rng)
                assert scan==decode_scan(row['generated_scan']['scan']),'Observer native sensor mismatch'
    # Independently reconstruct the leader's actual received-member information;
    # pacing must not come from the supervisor's other-robot state.
    leader_node=V2VEndpoint('leader')
    for row in traces['leader']:
        now=row['time_s']
        for event in row['radio']:
            if event.get('kind')=='beacon':assert leader_node.receive(event['message'].encode(),now)==event['accepted']
        goal,pace=pace_goal(leader_node,row['state'],now,road,spec['speed'])
        assert row['decision']['npc_speed_m_s']==goal
        assert all(row['decision'][k]==v for k,v in pace.items())
        assert math.isclose(row['command']['accel'],max(-6.,min(2.5,.8*(goal-row['state'][3]))),abs_tol=1e-10)
    node=V2VEndpoint('follower');control=SettlingFollower(node,road=road,speed=spec['speed'])
    rng=np.random.default_rng(np.random.SeedSequence([spec['seed'],11,zlib.crc32(b'follower')]))
    latency_rng=np.random.default_rng(np.random.SeedSequence([spec['seed'],13,zlib.crc32(b'follower')]))
    pending_radio={};pending_radar={};setpoint=0.;rows=[]
    for i,row in enumerate(traces['follower']):
        now=row['time_s'];node.observe_local(row['state'],now,now)
        for event in row['radio_incoming']:
            raw=event['message'].encode()
            if is_peer_scan(raw):
                observer,scan=decode_peer_scan(raw);assert observer in spec['connected']
                source=traces[observer][round(scan.observed_s/.05)-1]
                assert source['state']==list(scan.ego_state) and scan==decode_scan(source['generated_scan']['scan']),'Cooperative source mismatch'
            else:
                beacon=decode_beacon(raw);assert beacon.vehicle_id in spec['connected']
                source=traces[beacon.vehicle_id][round(beacon.observed_s/.05)-1]
                assert source['state']==list(beacon.state) and source['time_s']==beacon.observed_s,'Wire source mismatch'
            pending_radio[event['serial']]=event
        for event in row['radio']:
            incoming=pending_radio.pop(event['serial'])
            assert incoming['message']==event['message'] and now-.05-1e-9<incoming['due_s']<=now+1e-9
            raw=event['message'].encode()
            if is_peer_scan(raw):assert control.observe_peer_scan(raw,now)==event['accepted']
            else:assert node.receive(raw,now)==event['accepted']
        assert all(e['due_s']>now+1e-9 for e in pending_radio.values())
        if row['generated_scan'] is not None:
            scan=adapt_scan(row['generated_scan']['scan']['sequence'],now,row['state'],row['radar_targets'],spec['profile'],rng)
            due=now+spec['profile']['latency']+float(latency_rng.uniform(-spec['profile']['latency_jitter'],spec['profile']['latency_jitter']))
            assert asdict(scan)==row['generated_scan']['scan'] or scan==decode_scan(row['generated_scan']['scan'])
            assert due==row['generated_scan']['due_s']
            pending_radar[scan.sequence]=(scan,due)
        for event in row['radar']:
            scan=decode_scan(event['scan']);original,due=pending_radar.pop(scan.sequence)
            assert scan==original and now-.05-1e-9<due<=now+1e-9
            assert control.observe_scan(scan,now)==event['accepted']
        assert all(due>now+1e-9 for _,due in pending_radar.values())
        command,info=control.decide(now)
        assert asdict(command)==row['controller_command'] and info==row['decision'],'Native control replay mismatch'
        command,guard=native_braking_guard(command,info,row['state'],road)
        assert asdict(command)==row['command'] and guard==row['native_guard'],'Native stopping-reserve replay mismatch'
        states={n:data[i]['state'] for n,data in traces.items() if n!='follower'}
        rows.append(dict(time_s=now,before=row['state'],after=row['state'],traffic_before=states,
                         traffic_after=states,command=row['command'],decision=row['decision']))
    result=measure(rows,road,spec['speed'],native=True)
    result.update(case=spec['case'],speed=spec['speed'],seed=spec['seed'],native_samples=1400*len(traces),
        vehicles=len(traces),raw_sha256={n:digest(output/f'{n}.jsonl') for n in traces},
        motion_sha256={n:digest(output/f'{n}-motion.jsonl') for n in traces},
        scope='native physical curved/two-lane road; fallible anonymous perception, no real-world guarantee')
    return result


def run_one(job):
    output,case,speed,seed=job;output=Path(output).resolve()
    try:
        spec=configuration(case,speed,seed);world=prepare(output,spec)
        write(output/'config.json',spec)
        write(output/'provenance.json',dict(world_sha256=digest(world),controller_sha256=digest(output/'project/controllers/robust_vehicle/robust_vehicle.py')))
        env=os.environ.copy();env.update(LANS_V2V_REPO=str(ROOT),LANS_ROBUST_OUTPUT=str(output),
            PATH='/workspace/lans-venv/bin:'+env.get('PATH',''),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        with (output/'console.log').open('x') as log:
            subprocess.run(['bash',str(ROOT/'integrations/webots/run-webots.sh'),'--batch','--mode=fast',
                '--no-rendering','--stdout','--stderr',str(world)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=360)
        result=verify(output);write(output/'verification.json',result);return result
    except Exception:
        output.mkdir(parents=True,exist_ok=True);(output/'failure.txt').write_text(traceback.format_exc())
        return dict(passed=False,case=case,speed=speed,seed=seed,error='see failure.txt')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--stage',choices=('development','validation'),required=True)
    args=parser.parse_args();python=Path(args.python);root=Path(args.output).resolve()
    assert json.loads((python/'development/summary.json').read_text())['passed'],'Python development failed'
    plan=json.loads((python/'plan.json').read_text());verify_sources(plan['sources'])
    if args.stage=='development':
        root.mkdir(parents=True,exist_ok=False)
        hashes=freeze(root,[*runtime_files(),*[Path(__file__).with_name(n+'.py') for n in ('native','native_vehicle','world')],Path(__file__).with_name('NATIVE_PROTOCOL_V4.md')])
        write(root/'native-protocol.json',dict(sha256=digest(Path(__file__).with_name('NATIVE_PROTOCOL_V4.md'))))
        write(root/'plan.json',dict(cases=NATIVE_CASES,development_seeds=DEV_SEEDS,validation_seeds=VALIDATION_SEEDS,
            sources=hashes,python_plan_sha256=digest(python/'plan.json'),radio_range_m=150.,seconds=70.,
            development_speeds=DEV_SPEEDS,validation_speeds=(8.,12.)))
    native_plan=json.loads((root/'plan.json').read_text());verify_sources(native_plan['sources'])
    if args.stage=='validation':
        assert json.loads((python/'validation/summary.json').read_text())['passed'],'Python validation failed'
        assert json.loads((root/'development/summary.json').read_text())['passed'],'Native development failed'
    subprocess.run(['sha256sum','-c','../runtime-sha256.txt'],cwd=ROOT/'integrations/webots/.runtime',check=True)
    stage=root/args.stage;stage.mkdir(exist_ok=False)
    seeds=DEV_SEEDS if args.stage=='development' else VALIDATION_SEEDS
    speeds=DEV_SPEEDS if args.stage=='development' else (8.,12.)
    jobs=[(str(stage/f'{case}-{speed:g}-{seed}'),case,speed,seed) for case,speed,seed in itertools.product(NATIVE_CASES,speeds,seeds)]
    results=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run_one,job) for job in jobs]):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
    verify_sources(native_plan['sources'])
    results.sort(key=lambda r:(r['case'],r['speed'],r['seed']))
    write(stage/'summary.json',dict(passed=all(r['passed'] for r in results),results=results))
    if not all(r['passed'] for r in results):raise SystemExit('native cohort failed; evidence preserved')


if __name__=='__main__':main()
