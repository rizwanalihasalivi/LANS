"""Conditional native Radar validation; generate controllers without editing v1."""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import subprocess
from integrations.connected_v2v.demo import digest, write
from integrations.connected_v2v.webots.run import prepare
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.platoon import FollowingConfig
from integrations.connected_v2v.recovery.controller import FusionFollower, RangeObservation, METHODS
from integrations.connected_v2v.recovery.campaign import ROOT, check

CASES=('nominal','v2v_blackout','radar_blackout','dual_blackout')

RADAR_HOOK='''            radar_observation = None
            radar_accepted = None
            radar_targets = []
            if count % 10 == 0 and predecessor is not None:
                radar_targets = [dict(distance=t.distance, speed=t.speed, azimuth=t.azimuth) for t in radar.getTargets()]
                blocked = case in ('radar_blackout', 'dual_blackout') and name == 'follower-1' and 5. <= now < 6.5
                visible = [t for t in radar_targets if abs(t['azimuth']) <= .12 and t['distance'] > 0.]
                if visible and not blocked:
                    target = min(visible, key=lambda t:t['distance'])
                    gap = max(0., min(120., target['distance']*math.cos(target['azimuth'])+.1-4.6))
                    try:
                        observation = RangeObservation(predecessor, radar_sequence, now, tuple(state), gap, target['speed'])
                    except ValueError:
                        observation = None
                    radar_sequence += 1
                    if observation is not None:
                        radar_accepted = follower.observe_radar(observation, now)
                        radar_observation = asdict(observation)
'''


def controller_source():
    source=(ROOT/'integrations/connected_v2v/webots/connected_vehicle.py').read_text()
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1,('Controller template changed',old)
        source=source.replace(old,new)
    # ROOT must be on sys.path before importing the separately frozen controller.
    replace('from integrations.connected_v2v.node import V2VEndpoint',
            'from dataclasses import asdict\nfrom integrations.connected_v2v.recovery.controller import FusionFollower, RangeObservation\nfrom integrations.connected_v2v.node import V2VEndpoint')
    replace("follower = PlatoonController(endpoint, predecessor, following=FollowingConfig(cruise_speed_m_s=8.))",
            "follower = FusionFollower(endpoint, predecessor, method=os.environ['LANS_V2V_METHOD'], following=FollowingConfig(cruise_speed_m_s=8.))\n    radar = driver.getDevice('local_radar'); radar.enable(100)\n    radar_sequence = 0")
    replace("case == 'peer_blackout' and name == 'follower-1'", "case in ('v2v_blackout', 'dual_blackout') and name == 'leader'")
    replace('            scheduled_brake =',RADAR_HOOK+'            scheduled_brake =')
    replace('peers=endpoint.peers(now))),','peers=endpoint.peers(now), radar=radar_observation, radar_accepted=radar_accepted, radar_targets=radar_targets)),')
    compile(source,'connected_vehicle.py','exec')
    return source


def prepare_native(output):
    world=prepare(output)
    text=world.read_text()
    marker='GPS { name "v2v_gps" translation 1.4 0 0.4 }'
    assert text.count(marker)==3
    radar='Radar { name "local_radar" translation 1.4 0 0.4 minRange 0.5 maxRange 120 horizontalFieldOfView 0.25 verticalFieldOfView 0.4 minRadialSpeed 0 maxRadialSpeed 0 rangeNoise 0.05 speedNoise 0.02 occlusion TRUE }'
    world.write_text(text.replace(marker,marker+'\n    '+radar))
    (Path(output)/'project/controllers/connected_vehicle/connected_vehicle.py').write_text(controller_source())
    return world


def verify_native(output):
    output=Path(output);record=json.loads((output/'provenance.json').read_text())
    for name,expected in record['sources'].items():assert digest(ROOT/name)==expected,('Source changed',name)
    assert digest(output/'project/worlds/connected_convoy.wbt')==record['world_sha256']
    assert digest(output/'project/controllers/connected_vehicle/connected_vehicle.py')==record['controller_sha256']
    traces={};count=messages=0;fallbacks={};sources={}
    for name,pred in [('leader',None),('follower-1','leader'),('follower-2','follower-1')]:
        rows=[json.loads(s) for s in (output/f'{name}.jsonl').read_text().splitlines()]
        receipts=[json.loads(s) for s in (output/f'{name}-receipts.jsonl').read_text().splitlines()]
        summary=json.loads((output/f'{name}-summary.json').read_text())
        assert len(rows)==summary['samples']==240 and rows[-1]['time_s']>=12.-1e-8
        node=V2VEndpoint(name,expected_peers=[pred] if pred else ())
        follower=FusionFollower(node,pred,method=record['method'],following=FollowingConfig(cruise_speed_m_s=8.))
        event_index=0;speed=0.;previous_steer=0.;n_fallback=0;sensor_counts={}
        for i,row in enumerate(rows):
            now=row['time_s'];assert row['sample']==i and math.isclose(now,(i+1)*.05,abs_tol=1e-8)
            node.observe_local(row['state'],now,now)
            while event_index<len(receipts) and receipts[event_index]['received_s']<=now+1e-9:
                event=receipts[event_index];assert event['received_s']==now
                assert node.receive(event['message'].encode('utf-8', errors='surrogateescape'),now)==event['accepted'];event_index+=1
            if row['radar'] is not None:
                assert not (record['case'] in ('radar_blackout','dual_blackout') and name=='follower-1' and 5.<=now<6.5)
                obs=RangeObservation(**row['radar']);assert obs.observed_s==now
                targets=[t for t in row['radar_targets'] if abs(t['azimuth'])<=.12 and t['distance']>0]
                target=min(targets,key=lambda t:t['distance'])
                expected_gap=max(0.,min(120.,target['distance']*math.cos(target['azimuth'])+.1-4.6))
                assert obs.gap_m==expected_gap and obs.relative_speed_m_s==target['speed']
                assert follower.observe_radar(obs,now)==row['radar_accepted']
            command,decision=follower.decide(now,leader_accel=-2. if name=='leader' and 7.<=now<8. else None)
            assert asdict(command)==row['command'] and decision==row['decision'],'Native control replay mismatch'
            assert -6<=command.accel<=2.5 and abs(command.steering-previous_steer)<=.03+1e-9
            speed=max(0.,min(8.,speed+command.accel*.05))
            assert math.isclose(speed,row['commanded_speed_m_s'],abs_tol=1e-10)
            assert node.peers(now)==row['peers']
            previous_steer=command.steering
            n_fallback+=decision['source'] in ('fallback_brake','hold_brake')
            sensor=decision['sensor_source'];sensor_counts[sensor]=sensor_counts.get(sensor,0)+1
        assert event_index==len(receipts)==summary['received']
        assert rows[-1]['state'][0]>rows[0]['state'][0]+1.
        traces[name]=rows;fallbacks[name]=n_fallback;sources[name]=sensor_counts
        count+=len(rows);messages+=len(receipts)
    gaps=[];errors=[];progress={}
    for name,pred in [('follower-1','leader'),('follower-2','follower-1')]:
        progress[name]=traces[name][-1]['state'][0]-traces[name][0]['state'][0]
        for a,b in zip(traces[name],traces[pred]):
            gap=b['state'][0]-a['state'][0]-4.6;gaps.append(gap)
            errors.append((gap-6.-1.2*a['state'][3])**2)
    if record['case']=='v2v_blackout' and record['method']=='fusion':
        assert any(r['decision']['sensor_source']=='radar' and 5.4<=r['time_s']<6.5 for r in traces['follower-1'])
    return dict(passed=min(gaps)>0.,checks=dict(positive_longitudinal_gap=min(gaps)>0.),method=record['method'],case=record['case'],native_samples=count,
                radio_receipts=messages,min_gap_proxy_m=min(gaps),spacing_rms_m=math.sqrt(sum(errors)/len(errors)),
                progress_m=progress,fallback_samples=fallbacks,sensor_sources=sources,
                scope='native Radar and radio replay; no physical safety, timing or string-stability claim')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();study=check(a.study)
    for stage in ['development','confirmation']:
        assert json.loads((study/stage/'gate.json').read_text())['passed'],stage+' gate failed; native remains closed'
    root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).with_name('PROTOCOL.md'),
           *Path(__file__).parent.parent.glob('*.py'),*(ROOT/'integrations/connected_v2v').glob('*.py'),
           ROOT/'integrations/connected_v2v/webots/connected_vehicle.py',ROOT/'integrations/connected_v2v/webots/run.py',
           ROOT/'integrations/webots/worlds/vehicle_validation.wbt',ROOT/'integrations/unified_lans/traffic.py',
           ROOT/'integrations/unified_lans/physics.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    hashes={str(f.relative_to(ROOT)):digest(f) for f in files}
    write(root/'plan.json',dict(methods=list(METHODS),cases=list(CASES),sources=hashes,python_protocol_sha256=digest(study/'protocol.json')))
    runtime=ROOT/'integrations/webots/.runtime'
    subprocess.run(['sha256sum','-c','../runtime-sha256.txt'],cwd=runtime,check=True)
    results=[]
    for case in CASES:
        for method in METHODS:
            output=root/(case+'-'+method);world=prepare_native(output)
            write(output/'provenance.json',dict(case=case,method=method,sources=hashes,world_sha256=digest(world),
                controller_sha256=digest(output/'project/controllers/connected_vehicle/connected_vehicle.py')))
            env=os.environ.copy();env.update(LANS_V2V_REPO=str(ROOT),LANS_V2V_NATIVE_OUTPUT=str(output),
                LANS_V2V_NATIVE_CASE=case,LANS_V2V_NATIVE_SECONDS='12',LANS_V2V_METHOD=method,
                PATH='/workspace/lans-venv/bin:'+env.get('PATH',''),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
            with (output/'console.log').open('x') as log:
                subprocess.run(['bash',str(ROOT/'integrations/webots/run-webots.sh'),'--batch','--mode=fast','--no-rendering',
                    '--stdout','--stderr',str(world)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
            result=verify_native(output);write(output/'verification.json',result);results.append(result)
            print(json.dumps(result),flush=True)
    write(root/'summary.json',results)


if __name__=='__main__':main()
