"""Separate feedback gains from the native follower speed-cap correction."""
import argparse
from dataclasses import asdict
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
from integrations.connected_v2v.demo import digest,write
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.recovery.controller import RangeObservation
from integrations.connected_v2v.recovery.native import run as v2_native
from integrations.connected_v2v.formation.controller import FormationFollower,following_for,VARIANTS
from integrations.connected_v2v.formation.campaign import ROOT,check,files

CASES=('nominal','v2v_blackout','radar_blackout','dual_blackout')
ADAPTERS=('legacy','recovery')


def controller_source():
    source=v2_native.controller_source()
    def change(old,new):
        nonlocal source
        assert source.count(old)==1,('Native template changed',old)
        source=source.replace(old,new)
    change('from integrations.connected_v2v.recovery.controller import FusionFollower, RangeObservation',
           'from integrations.connected_v2v.recovery.controller import RangeObservation\nfrom integrations.connected_v2v.formation.controller import FormationFollower as FusionFollower, following_for')
    change('following=FollowingConfig(cruise_speed_m_s=8.)',"following=following_for(os.environ['LANS_V2V_METHOD'],8.)")
    change('commanded_speed = max(0., min(8., commanded_speed+command.accel*.05))',
           "native_cap = 8. if name == 'leader' or os.environ['LANS_FORMATION_ADAPTER'] == 'legacy' else 16.\n            commanded_speed = max(0., min(native_cap, commanded_speed+command.accel*.05))")
    change('peers=endpoint.peers(now), radar=', 'peers=endpoint.peers(now), native_cap_m_s=native_cap, radar=')
    change('state=state, command=', "state=state, native_pose=dict(position=list(position), rpy=imu.getRollPitchYaw()), command=")
    compile(source,'connected_vehicle.py','exec')
    return source


def prepare_native(output):
    world=v2_native.prepare_native(output)
    text=world.read_text()
    assert text.count('translation 50 0 -0.1')==1 and text.count('size 200 100 0.2')==2
    text=text.replace('translation 50 0 -0.1','translation 500 0 -0.1')
    world.write_text(text.replace('size 200 100 0.2','size 2000 100 0.2'))
    (Path(output)/'project/controllers/connected_vehicle/connected_vehicle.py').write_text(controller_source())
    return world


def validate_pose(row):
    position=row['native_pose']['position'];rpy=row['native_pose']['rpy']
    assert all(math.isfinite(v) for v in [*position,*rpy]),'Nonfinite native pose'
    assert -495.<=position[0]<=1495. and abs(position[1])<=1.75,'Car left the declared road/corridor'
    assert .1<=position[2]<=2.,'Native car height invalid (off-road/falling)'
    assert abs(rpy[0])<=.35 and abs(rpy[1])<=.35,'Native car tilted/overturned'
    assert abs(math.atan2(math.sin(rpy[2]),math.cos(rpy[2])))<=.2,'Native forward-heading envelope violated'


def verify_native(output):
    output=Path(output);record=json.loads((output/'provenance.json').read_text())
    for name,expected in record['sources'].items():assert digest(ROOT/name)==expected,('Source changed',name)
    assert digest(output/'project/worlds/connected_convoy.wbt')==record['world_sha256']
    assert digest(output/'project/controllers/connected_vehicle/connected_vehicle.py')==record['controller_sha256']
    traces={};samples=messages=0;fallbacks={};peaks={};accelerations={}
    for name,pred in [('leader',None),('follower-1','leader'),('follower-2','follower-1')]:
        rows=[json.loads(s) for s in (output/f'{name}.jsonl').read_text().splitlines()]
        events=[json.loads(s) for s in (output/f'{name}-receipts.jsonl').read_text().splitlines()]
        summary=json.loads((output/f'{name}-summary.json').read_text())
        assert len(rows)==summary['samples']==600 and rows[-1]['time_s']>=30.-1e-8
        node=V2VEndpoint(name,expected_peers=[pred] if pred else ())
        control=FormationFollower(node,pred,method=record['variant'],following=following_for(record['variant'],8.))
        event_index=0;setpoint=previous_steer=0.;fallback=0
        for i,row in enumerate(rows):
            now=row['time_s'];assert row['sample']==i and math.isclose(now,(i+1)*.05,abs_tol=1e-8)
            validate_pose(row)
            node.observe_local(row['state'],now,now)
            while event_index<len(events) and events[event_index]['received_s']<=now+1e-9:
                event=events[event_index];assert event['received_s']==now
                assert node.receive(event['message'].encode(),now)==event['accepted'];event_index+=1
            if row['radar'] is not None:
                assert not (record['case'] in ('radar_blackout','dual_blackout') and name=='follower-1' and 5.<=now<6.5)
                observation=RangeObservation(**row['radar']);assert observation.observed_s==now
                targets=[t for t in row['radar_targets'] if abs(t['azimuth'])<=.12 and t['distance']>0]
                target=min(targets,key=lambda t:t['distance'])
                assert observation.gap_m==max(0.,min(120.,target['distance']*math.cos(target['azimuth'])+.1-4.6))
                assert observation.relative_speed_m_s==target['speed']
                assert control.observe_radar(observation,now)==row['radar_accepted']
            command,decision=control.decide(now,leader_accel=-2. if name=='leader' and 7.<=now<8. else None)
            assert asdict(command)==row['command'] and decision==row['decision'],'Native control replay mismatch'
            assert -6<=command.accel<=2.5 and abs(command.steering-previous_steer)<=.03+1e-9
            cap=8. if name=='leader' or record['adapter']=='legacy' else 16.
            assert row['native_cap_m_s']==cap
            setpoint=max(0.,min(cap,setpoint+command.accel*.05))
            assert math.isclose(setpoint,row['commanded_speed_m_s'],abs_tol=1e-10)
            assert node.peers(now)==row['peers']
            previous_steer=command.steering
            fallback+=decision['source'] in ('hold_brake','fallback_brake')
        assert event_index==len(events)==summary['received']
        assert rows[-1]['state'][0]>rows[0]['state'][0]+1.
        traces[name]=rows;samples+=len(rows);messages+=len(events);fallbacks[name]=fallback
        peaks[name]=max(r['state'][3] for r in rows)
        measured=[(rows[i]['state'][3]-rows[i-1]['state'][3])/.05 for i in range(1,len(rows))]
        accelerations[name]=dict(min_m_s2=min(measured),max_m_s2=max(measured))
    errors=[];first20=[];tail=[];gaps=[];progress={}
    for name,pred in [('follower-1','leader'),('follower-2','follower-1')]:
        progress[name]=traces[name][-1]['state'][0]-traces[name][0]['state'][0]
        for row,front in zip(traces[name],traces[pred]):
            assert row['time_s']==front['time_s']
            gap=front['state'][0]-row['state'][0]-4.6;error=gap-6.-1.2*row['state'][3]
            gaps.append(gap);errors.append(error**2)
            if row['time_s']<=20.+1e-9:first20.append(error**2)
            if row['time_s']>=25.-1e-9:tail.append(error**2)
    return dict(passed=min(gaps)>0.,case=record['case'],variant=record['variant'],adapter=record['adapter'],
                native_samples=samples,radio_receipts=messages,min_gap_proxy_m=min(gaps),
                spacing_rms_m=math.sqrt(math.fsum(errors)/len(errors)),
                first20_spacing_rms_m=math.sqrt(math.fsum(first20)/len(first20)),
                final5_spacing_rms_m=math.sqrt(math.fsum(tail)/len(tail)),
                progress_m=progress,peak_speeds_m_s=peaks,speed_derived_accel_range=accelerations,fallback_samples=fallbacks,
                scope='native feedback/adapter factorial; no physical safety or real-time guarantee')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    study=check(a.study)
    for stage in ['development','confirmation']:assert json.loads((study/stage/'gate.json').read_text())['passed'],stage+' gate failed'
    root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False)
    dependencies={*files(),*Path(__file__).parent.glob('*.py'),
        ROOT/'integrations/connected_v2v/recovery/native/run.py',ROOT/'integrations/connected_v2v/webots/connected_vehicle.py',
        ROOT/'integrations/connected_v2v/webots/run.py',ROOT/'integrations/webots/worlds/vehicle_validation.wbt'}
    hashes={str(path.relative_to(ROOT)):digest(path) for path in sorted(dependencies)}
    write(root/'plan.json',dict(cases=list(CASES),variants=list(VARIANTS),adapters=list(ADAPTERS),seconds=30.,
        source_hashes=hashes,python_protocol_sha256=digest(study/'protocol.json'),
        fixture='longroad-v1',road_x_bounds_m=[-500.,1500.],
        correction='original 200m fixture exhausted in 30s; old runs preserved, controller/settings unchanged'))
    for name in hashes:
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    subprocess.run(['sha256sum','-c','../runtime-sha256.txt'],cwd=ROOT/'integrations/webots/.runtime',check=True)
    results=[]
    for case,variant,adapter in itertools.product(CASES,VARIANTS,ADAPTERS):
        output=root/f'{case}-{variant}-{adapter}';world=prepare_native(output)
        write(output/'provenance.json',dict(case=case,variant=variant,adapter=adapter,sources=hashes,
            world_sha256=digest(world),controller_sha256=digest(output/'project/controllers/connected_vehicle/connected_vehicle.py')))
        env=os.environ.copy();env.update(LANS_V2V_REPO=str(ROOT),LANS_V2V_NATIVE_OUTPUT=str(output),LANS_V2V_NATIVE_CASE=case,
            LANS_V2V_NATIVE_SECONDS='30',LANS_V2V_METHOD=variant,LANS_FORMATION_ADAPTER=adapter,
            PATH='/workspace/lans-venv/bin:'+env.get('PATH',''),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        with (output/'console.log').open('x') as log:
            subprocess.run(['bash',str(ROOT/'integrations/webots/run-webots.sh'),'--batch','--mode=fast','--no-rendering','--stdout','--stderr',str(world)],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
        result=verify_native(output);write(output/'verification.json',result);results.append(result)
        print(json.dumps(result),flush=True)
    write(root/'summary.json',results)


if __name__=='__main__':main()
