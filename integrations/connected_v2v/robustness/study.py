"""Frozen staged Python robustness trials; no final comparison or training."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
import heapq
import itertools
import json
from pathlib import Path
import shutil
import traceback
import zlib
import numpy as np
from integrations.connected_v2v.autonomy.study import ROOT,digest,write,decode_scan
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.network import Link,SimulatedChannel
from integrations.connected_v2v.messages import decode_beacon
from integrations.unified_lans.physics import advance
from .controller import RobustFollower
from .scenarios import PROFILES,Scene,SPEEDS,DEV_SEEDS,VALIDATION_SEEDS,radar_scan
from .metrics import measure
from .relay import PendingRelays
from .perception import encode_peer_scan


def runtime_files():
    names=['integrations/connected_v2v/robustness/'+s+'.py' for s in ('__init__','controller','scenarios','study','metrics','relay','perception')]
    names+=['integrations/connected_v2v/autonomy/'+s+'.py' for s in ('__init__','controller','road','study')]
    names+=['integrations/connected_v2v/'+s+'.py' for s in ('__init__','messages','node','network','platoon')]
    names+=['integrations/connected_v2v/formation/controller.py','integrations/connected_v2v/recovery/controller.py',
            'integrations/unified_lans/physics.py','integrations/unified_lans/traffic.py',
            'controllers/lqr_controller.py','models/bicycle_model.py']
    return [ROOT/name for name in names]


def freeze(root,files):
    hashes={str(p.relative_to(ROOT)):digest(p) for p in files}
    for name in hashes:
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return hashes


def verify_sources(hashes):
    for name,expected in hashes.items():assert digest(ROOT/name)==expected,('Runtime source changed',name)


def run_episode(output,case,speed,seed,*,seconds=32.):
    if case not in PROFILES or seconds<=0 or abs(seconds/.05-round(seconds/.05))>1e-8:
        raise ValueError('known case and complete positive ticks required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    scene=Scene(case,speed,seed);p=scene.profile
    node=V2VEndpoint('follower');control=RobustFollower(node,road=scene.road,speed=speed)
    nodes={n:V2VEndpoint(n) for n in scene.connected};nodes['follower']=node
    pending={n:PendingRelays() for n in nodes}
    channel=SimulatedChannel(seed+23,default=Link(delay_s=.05,jitter_s=.025,loss=.1,duplicate=.1,
        blackout=((11.,12.5),) if p.radio_blackout else ()))
    sensor_rng=np.random.default_rng(np.random.SeedSequence([seed,11]))
    latency_rng=np.random.default_rng(np.random.SeedSequence([seed,13]))
    peer_rng={name:np.random.default_rng(np.random.SeedSequence([seed,41,zlib.crc32(name.encode())])) for name in scene.connected}
    peer_queue=[];serial=0
    ego=np.array([0.,0.,0.,speed,0.,0.]);queue=[];rows=[]
    write(output/'case.json',dict(case=case,speed=speed,seed=seed,seconds=seconds,profile=asdict(p),initial=ego.tolist()))
    for tick in range(round(seconds/.05)):
        now=tick*.05;traffic=scene.states(now)
        node.observe_local(ego,now,now)
        if tick%2==0:
            positions={**traffic,'follower':ego}
            for name,sender in nodes.items():
                payload=sender.publish(positions[name],now,now)
                forwarded=pending[name].take(now,scene.road)
                for raw in [payload]+([forwarded] if forwarded is not None else []):
                    origin=decode_beacon(raw).vehicle_id
                    for receiver in nodes:
                        if receiver in (name,origin):continue
                        # SimulatedChannel's source is the original beacon ID;
                        # distance is supplied from the ACTUAL transmitter/relay.
                        channel.transmit(origin,receiver,raw,now,distance_m=float(np.linalg.norm(positions[name][:2]-positions[receiver][:2])))
            if not(p.radar_blackout and 11.<=now<12.5):
                scan=radar_scan(tick//2,now,ego,traffic,p,sensor_rng)
                due=now+p.latency+float(latency_rng.uniform(-p.latency_jitter,p.latency_jitter))
                heapq.heappush(queue,(due,scan.sequence,scan))
            if not(p.radio_blackout and 11.<=now<12.5):
                for name in scene.connected:
                    if np.linalg.norm(traffic[name][:2]-ego[:2])>150.:continue
                    others={**traffic,'follower':ego};others.pop(name)
                    scan=radar_scan(tick//2,now,traffic[name],others,p,peer_rng[name])
                    payload=encode_peer_scan(name,scan);serial+=1
                    heapq.heappush(peer_queue,(now+.05,serial,payload))
        radio=channel.deliver(now,nodes);radar=[]
        for event in radio:
            if event['accepted']:pending[event['receiver']].add(event['message'].encode())
        while queue and queue[0][0]<=now+1e-9:
            _,_,scan=heapq.heappop(queue)
            radar.append(dict(scan=asdict(scan),accepted=control.observe_scan(scan,now)))
        peers=[]
        while peer_queue and peer_queue[0][0]<=now+1e-9:
            _,_,payload=heapq.heappop(peer_queue)
            if p.radio_blackout and 11.<=now<12.5:continue
            peers.append(dict(message=payload.decode(),accepted=control.observe_peer_scan(payload,now)))
        command,info=control.decide(now);after=advance(ego,command,.05)
        rows.append(dict(tick=tick,time_s=now,before=ego.tolist(),after=after.tolist(),
            traffic_before={n:z.tolist() for n,z in traffic.items()},
            traffic_after={n:z.tolist() for n,z in scene.states(now+.05).items()},
            radio=radio,radar=radar,peer_scans=peers,command=asdict(command),decision=info))
        ego=after
    (output/'ticks.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    result=measure(rows,scene.road,speed)
    result.update(case=case,speed=speed,seed=seed,raw_sha256=digest(output/'ticks.jsonl'),case_sha256=digest(output/'case.json'))
    write(output/'summary.json',result);write(output/'replay.json',replay(output))
    return result


def replay(output):
    output=Path(output);spec=json.loads((output/'case.json').read_text());summary=json.loads((output/'summary.json').read_text())
    assert digest(output/'case.json')==summary['case_sha256'] and digest(output/'ticks.jsonl')==summary['raw_sha256']
    rows=[json.loads(s) for s in (output/'ticks.jsonl').read_text().splitlines()]
    assert len(rows)==round(spec['seconds']/.05)
    scene=Scene(spec['case'],spec['speed'],spec['seed']);p=scene.profile
    assert spec['profile']==asdict(p)
    node=V2VEndpoint('follower');control=RobustFollower(node,road=scene.road,speed=scene.speed)
    nodes={name:V2VEndpoint(name) for name in scene.connected};nodes['follower']=node
    sensor_rng=np.random.default_rng(np.random.SeedSequence([spec['seed'],11]))
    latency_rng=np.random.default_rng(np.random.SeedSequence([spec['seed'],13]))
    expected={};previous=spec['initial']
    for tick,row in enumerate(rows):
        now=tick*.05;assert row['tick']==tick and row['time_s']==now
        np.testing.assert_array_equal(row['before'],previous)
        node.observe_local(row['before'],now,now)
        if tick%2==0 and not(p.radar_blackout and 11.<=now<12.5):
            scan=radar_scan(tick//2,now,np.array(row['before']),scene.states(now),p,sensor_rng)
            due=now+p.latency+float(latency_rng.uniform(-p.latency_jitter,p.latency_jitter))
            expected[scan.sequence]=(scan,due)
        for event in row['radio']:
            beacon=decode_beacon(event['message'].encode());assert beacon.vehicle_id in nodes
            truth=rows[round(beacon.observed_s/.05)]['before'] if beacon.vehicle_id=='follower' else scene.states(beacon.observed_s)[beacon.vehicle_id]
            np.testing.assert_array_equal(beacon.state,truth)
            assert event['received_s']==now and nodes[event['receiver']].receive(event['message'].encode(),now)==event['accepted']
        for event in row['radar']:
            scan=decode_scan(event['scan']);original,due=expected.pop(scan.sequence)
            assert scan==original and due<=now+1e-9 and due>now-.05-1e-9,'Sensor mismatch'
            assert control.observe_scan(scan,now)==event['accepted']
        assert all(due>now+1e-9 for _,due in expected.values()),'Missing sensor delivery'
        for event in row['peer_scans']:
            assert control.observe_peer_scan(event['message'].encode(),now)==event['accepted']
        command,info=control.decide(now)
        assert asdict(command)==row['command'] and info==row['decision'],'Control replay mismatch'
        np.testing.assert_array_equal(advance(row['before'],command,.05),row['after'])
        for key,stamp in [('traffic_before',now),('traffic_after',now+.05)]:
            states=scene.states(stamp);assert set(states)==set(row[key])
            for name in states:np.testing.assert_array_equal(states[name],row[key][name])
        previous=row['after']
    metrics=measure(rows,scene.road,scene.speed)
    assert all(summary[k]==v for k,v in metrics.items()),'Aggregate mismatch'
    return dict(passed=True,ticks=len(rows),sensor_input_replay=True,control_replay=True,shared_bicycle_replay=True)


def task(args):
    output,case,speed,seed=args
    try:return run_episode(output,case,speed,seed)
    except Exception:
        path=Path(output);path.mkdir(parents=True,exist_ok=True)
        (path/'failure.txt').write_text(traceback.format_exc())
        return dict(passed=False,case=case,speed=speed,seed=seed,error='see failure.txt')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--stage',choices=('development','validation'),required=True)
    args=parser.parse_args();root=Path(args.output).resolve()
    if args.stage=='development':
        root.mkdir(parents=True,exist_ok=False)
        hashes=freeze(root,runtime_files())
        write(root/'plan.json',dict(cases=list(PROFILES),speeds=SPEEDS,development_seeds=DEV_SEEDS,
            validation_seeds=VALIDATION_SEEDS,seconds=32.,sources=hashes))
        shutil.copyfile(Path(__file__).with_name('PROTOCOL.md'),root/'PROTOCOL.md')
    plan=json.loads((root/'plan.json').read_text());verify_sources(plan['sources'])
    if args.stage=='validation':assert json.loads((root/'development/summary.json').read_text())['passed'],'Development gate failed'
    stage=root/args.stage;stage.mkdir(exist_ok=False)
    seeds=DEV_SEEDS if args.stage=='development' else VALIDATION_SEEDS
    jobs=[(str(stage/f'{case}-{speed:g}-{seed}'),case,speed,seed) for case,speed,seed in itertools.product(PROFILES,SPEEDS,seeds)]
    results=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(task,j) for j in jobs]):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
    results.sort(key=lambda r:(r['case'],r['speed'],r['seed']))
    verify_sources(plan['sources'])
    write(stage/'summary.json',dict(passed=all(r['passed'] for r in results),results=results))


if __name__=='__main__':main()
