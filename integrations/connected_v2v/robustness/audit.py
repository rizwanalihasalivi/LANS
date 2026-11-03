"""Independent stdlib scoring/wire audit. Imports no controller, plant or NumPy."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path


def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project(z,radius):
    return (radius*math.atan2(z[0],radius-z[1]),radius-math.hypot(z[0],radius-z[1])) if radius else (z[0],z[1])


def collision(a,b):
    axes=[(math.cos(z[2]),math.sin(z[2])) for z in (a,b)]
    normals=[(-y,x) for x,y in axes]
    dot=lambda a,b:a[0]*b[0]+a[1]*b[1]
    delta=(b[0]-a[0],b[1]-a[1])
    for axis in axes+normals:
        radius=sum(2.3*abs(dot(t,axis))+.9*abs(dot(n,axis)) for t,n in zip(axes,normals))
        if abs(dot(delta,axis))>radius:return False
    return True


def score(data,radius,speed,native=False):
    result=dict(collisions=0,bound_violations=0,stale_source_ticks=0,blind_brake_violations=0,corridor_ticks=0)
    acquired=returned=0;positive_peer_frames=0;previous_steering=0.
    for row in data:
        now=row['time_s'];ego=row['after'];info=row['decision'];cmd=row['command']
        result['collisions']+=sum(collision(a,b) for a,b in itertools.combinations([ego,*row['traffic_after'].values()],2))
        result['bound_violations']+=not(-6.<=cmd['accel']<=2.5 and abs(cmd['steering'])<=.5+1e-9 and abs(cmd['steering']-previous_steering)<=.03+1e-9)
        previous_steering=cmd['steering']
        result['blind_brake_violations']+=info['selection_brake'] and cmd['accel']!=-6.
        result['corridor_ticks']+=abs(project(ego,radius)[1])>1.75
        if info['sensor_source'] in ('radar','v2v'):
            age=now-info['selected_observed_s']
            result['stale_source_ticks']+=not(-1e-9<=age<=(.2 if info['sensor_source']=='radar' else .4)+1e-9)
        for evidence in info.get('peer_exit_evidence',[]):
            assert -1e-9<=now-evidence['observed_s']<=.2+1e-9,'Stale cooperative exit evidence'
            positive_peer_frames+=1
        target='intruder' if 11.5<=now<18. else 'leader' if now>=(23. if native else 22.) else None
        if target and info['target_gap_m'] is not None and info['sensor_source'] in ('v2v','radar'):
            gap=project(row['traffic_before'][target],radius)[0]-project(row['before'],radius)[0]-4.6
            if abs(gap-info['target_gap_m'])<2.:
                acquired+=target=='intruder';returned+=target=='leader'
    result={k:int(v) for k,v in result.items()}
    result.update(progress_m=project(data[-1]['after'],radius)[0]-project(data[0]['before'],radius)[0],
                  acquired_intruder_ticks=acquired,recovered_leader_ticks=returned,ticks=len(data))
    result['passed']=not any(result[k] for k in ('collisions','bound_violations','stale_source_ticks','blind_brake_violations','corridor_ticks')) and result['progress_m']>max(25.,.4*speed*len(data)*.05) and acquired>=20 and returned>=20
    return result,positive_peer_frames


def compare(actual,stored):
    for key,value in actual.items():
        assert math.isclose(value,stored[key],rel_tol=0.,abs_tol=1e-8) if isinstance(value,float) else value==stored[key],(key,value,stored[key])


def check_freeze(root):
    plan=read(root/'plan.json')
    for name,expected in plan['sources'].items():assert sha(root/'source'/name)==expected,('Source freeze changed',name)


def check_python(root,stage):
    root=Path(root);check_freeze(root);summary=read(root/stage/'summary.json')
    total=peer_frames=0
    for stored in summary['results']:
        path=root/stage/f"{stored['case']}-{stored['speed']:g}-{stored['seed']}"
        assert read(path/'summary.json')==stored and read(path/'replay.json')['passed']
        assert sha(path/'ticks.jsonl')==stored['raw_sha256'] and sha(path/'case.json')==stored['case_sha256']
        spec=read(path/'case.json');data=rows(path/'ticks.jsonl');assert len(data)==640
        actual,peers=score(data,spec['profile']['radius'],spec['speed']);compare(actual,stored)
        assert actual['passed'],('Python gate failed',path.name)
        for row in data:
            for event in row['peer_scans']:
                obj=json.loads(event['message']);scan=obj['scan'];source=round(scan['observed_s']/.05)
                assert scan['ego_state']==data[source]['traffic_before'][obj['observer_id']]
                assert row['time_s']>=scan['observed_s'] and not scan['complete']
        total+=len(data);peer_frames+=peers
    expected=72 if stage=='development' else 240
    assert len(summary['results'])==expected and summary['passed']
    return dict(passed=True,episodes=expected,ego_ticks=total,peer_evidence_samples=peer_frames)


def check_native(root,stage,allow_failed=False):
    root=Path(root);check_freeze(root);summary=read(root/stage/'summary.json')
    total=peer_frames=relays=0;failures=[]
    for stored in summary['results']:
        path=root/stage/f"{stored['case']}-{stored['speed']:g}-{stored['seed']}"
        assert read(path/'verification.json')==stored
        spec=read(path/'config.json');provenance=read(path/'provenance.json')
        assert sha(path/'project/worlds/robust.wbt')==provenance['world_sha256']
        assert sha(path/'project/controllers/robust_vehicle/robust_vehicle.py')==provenance['controller_sha256']
        traces={n:rows(path/f'{n}.jsonl') for n in spec['starts']}
        assert all(len(v)==700 for v in traces.values())
        radio_range=spec.get('radio_range_m',150.)
        assert radio_range==read(root/'plan.json').get('radio_range_m',150.)
        world=(path/'project/worlds/robust.wbt').read_text()
        controller=(path/'project/controllers/robust_vehicle/robust_vehicle.py').read_text()
        assert world.count(f'range {radio_range:g}')==len(traces)
        assert controller.count(f'emitter.setRange({radio_range:g}.)')==1
        for name,data in traces.items():
            assert sha(path/f'{name}.jsonl')==stored['raw_sha256'][name]
            accepted=set();previous_steering=0.
            for row in data:
                now=row['time_s'];forwarded=0
                command=row['command']
                assert -6.<=command['accel']<=2.5 and abs(command['steering'])<=.5+1e-9 and abs(command['steering']-previous_steering)<=.03+1e-9,'Native requested bounds/rate'
                previous_steering=command['steering']
                for event in row['radio']:
                    if event['accepted'] and event.get('kind','beacon')=='beacon':accepted.add(event['message'])
                for raw in row['transmitted']:
                    assert name in spec['connected'],'Non-connected transmitter'
                    obj=json.loads(raw)
                    if obj.get('kind')=='range_scan':
                        assert obj['observer_id']==name and obj['scan']==row['generated_scan']['scan']
                    else:
                        origin=obj['vehicle_id'];source=traces[origin][round(obj['observed_s']/.05)-1]
                        assert source['state']==obj['state'] and source['time_s']==obj['observed_s']
                        if origin!=name:
                            assert raw in accepted and -1e-9<=now-obj['observed_s']<=.25+1e-9
                            forwarded+=1;relays+=1
                assert forwarded<=1,'Relay packet budget exceeded'
        data=[]
        for i,row in enumerate(traces['follower']):
            traffic={n:v[i]['state'] for n,v in traces.items() if n!='follower'}
            data.append(dict(time_s=row['time_s'],before=row['state'],after=row['state'],
                traffic_before=traffic,traffic_after=traffic,command=row['command'],decision=row['decision']))
            for event in row['radio_incoming']:
                obj=json.loads(event['message'])
                if obj.get('kind')=='range_scan':
                    observer=obj['observer_id'];scan=obj['scan'];source=traces[observer][round(scan['observed_s']/.05)-1]
                    assert scan['ego_state']==source['state'] and scan==source['generated_scan']['scan']
                else:
                    source=traces[obj['vehicle_id']][round(obj['observed_s']/.05)-1]
                    assert source['state']==obj['state'] and source['time_s']==obj['observed_s']
        actual,peers=score(data,spec['profile']['radius'],spec['speed'],native=True);compare(actual,stored)
        if not actual['passed']:
            failures.append(path.name)
            assert allow_failed,('Native gate failed',path.name)
        total+=sum(map(len,traces.values()));peer_frames+=peers
    expected=12 if stage=='development' else 36
    assert len(summary['results'])==expected and summary['passed']==(not failures)
    return dict(passed=True,workflow_passed=not failures,gate_failures=failures,episodes=expected,native_samples=total,peer_evidence_samples=peer_frames,original_byte_relays=relays)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',required=True);parser.add_argument('--native',required=True)
    parser.add_argument('--stage',choices=('development','validation','all'),default='all')
    args=parser.parse_args();stages=('development','validation') if args.stage=='all' else (args.stage,)
    print(json.dumps({stage:dict(python=check_python(args.python,stage),native=check_native(args.native,stage)) for stage in stages},indent=2))


if __name__=='__main__':main()
