"""Independent stdlib score, source, identity, pacing and native-motion audit.

Imports neither the controller, plant nor the simulation scoring function.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path


def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def project(z,R):return (R*math.atan2(z[0],R-z[1]),R-math.hypot(z[0],R-z[1])) if R else (z[0],z[1])
def close(a,b):return math.isclose(a,b,rel_tol=0.,abs_tol=1e-8)


def collision(a,b):
    axes=[(math.cos(z[2]),math.sin(z[2])) for z in (a,b)]
    normals=[(-y,x) for x,y in axes]
    dot=lambda a,b:a[0]*b[0]+a[1]*b[1]
    delta=(b[0]-a[0],b[1]-a[1])
    return all(abs(dot(delta,n))<=sum(2.3*abs(dot(e,n))+.9*abs(dot(f,n)) for e,f in zip(axes,normals)) for n in axes+normals)


def canonical(z,R):
    s,d=project(z,R);heading=s/R if R else 0.
    angle=z[2]-heading
    return s,d,z[3]*math.cos(angle)-z[4]*math.sin(angle)


def score(data,R,speed,native=False):
    counts=dict(collisions=0,bound_violations=0,stale_source_ticks=0,blind_brake_violations=0,corridor_ticks=0)
    acquired=returned=0;stable=longest=settled=0;stable_time=settled_time=None;prev=0.
    tail=[];relative=[];headspeed=[];correct_tail=0;exit_time=23. if native else 22.
    tail_start=data[-1]['time_s']-4.95
    following_count=0;following_target=following_stamp=None;observed_cutin=False
    admitted_stamps=set()
    for row in data:
        now=row['time_s'];ego=row['before'];cmd=row['command'];info=row['decision'];traffic=row['traffic_before']
        counts['collisions']+=sum(collision(a,b) for a,b in itertools.combinations([row['after'],*row['traffic_after'].values()],2))
        counts['bound_violations']+=not(-6.<=cmd['accel']<=2.5 and abs(cmd['steering'])<=.5+1e-9 and abs(cmd['steering']-prev)<=.03+1e-9)
        prev=cmd['steering']
        counts['blind_brake_violations']+=bool(info['selection_brake'] and cmd['accel']!=-6.)
        counts['corridor_ticks']+=abs(project(row['after'],R)[1])>1.75
        fresh=info['sensor_source'] in ('radar','v2v') and info['selected_observed_s'] is not None
        if fresh:counts['stale_source_ticks']+=not(-1e-9<=now-info['selected_observed_s']<=(.2 if info['sensor_source']=='radar' else .4)+1e-9)
        if info['sensor_source']=='v2v':assert info['selected_radio_id'] is not None,'radio target lacks original identity'
        s=project(ego,R)[0];head=traffic['leader'];gap=project(head,R)[0]-s-4.6
        correct=fresh and info['target_gap_m'] is not None and abs(info['target_gap_m']-gap)<2. and info['selected_radio_id'] in (None,'leader')
        if 11.5<=now<18. and fresh and info['target_gap_m'] is not None:
            intruder_gap=project(traffic['intruder'],R)[0]-s-4.6
            acquired+=abs(info['target_gap_m']-intruder_gap)<2.
        if now>=exit_time:
            returned+=bool(fresh and info['target_gap_m'] is not None and abs(info['target_gap_m']-gap)<2.)
            stable=stable+1 if correct else 0;longest=max(longest,stable)
            if stable>=40 and stable_time is None:stable_time=max(0.,now-exit_time-1.95)
            error=gap-6.-1.2*ego[3]
            settled=settled+1 if correct and abs(error)<=2. and abs(ego[3]-head[3])<=.5 else 0
            if settled>=40 and settled_time is None:settled_time=max(0.,now-exit_time-1.95)
        if now>=tail_start-1e-8:
            tail.append(gap-6.-1.2*ego[3]);relative.append(ego[3]-head[3]);headspeed.append(head[3]-speed);correct_tail+=bool(correct)
        assert info['radio_range_m']==150.
        assert info['formation_mode_used'] in ('following','recovering')
        if 'lateral_guard_mode' in info:
            expected_mode='lane_aware' if info['formation_mode_used']=='recovering' or following_count>=3 else 'conservative'
            assert info['lateral_guard_mode']==expected_mode,'guard enabled before observed admission/confirmation'
            if expected_mode=='lane_aware' and info['formation_mode_used']!='recovering':
                assert len(admitted_stamps)>=3,'trace lacks three genuinely distinct admission stamps'
            if info['selection_event']=='cut_in':observed_cutin=True
            if info['selected_target']!=following_target:
                following_target=info['selected_target'];following_count=0;following_stamp=None
                admitted_stamps=set()
            stamp=info['selected_observed_s']
            if (observed_cutin and fresh and not info['selection_brake']
                    and (following_stamp is None or stamp>following_stamp)):
                following_count=min(3,following_count+1);following_stamp=stamp
                admitted_stamps.add(stamp)
            assert info['confirmed_following_frames']==following_count
        for obj in info['guard_objects']:
            end=obj['d']+.6*obj['lateral']
            minimum=0. if obj['d']*end<=0 else min(abs(obj['d']),abs(end))
            assert close(obj['lateral_clearance_lower_m'],minimum-.54-.15)
            relevant=minimum-.54-.15<=2.4 if info.get('lateral_guard_mode',info['formation_mode_used']) in ('lane_aware','recovering') else abs(obj['d'])<=4.5
            assert obj['relevant']==relevant
    rms=lambda z:math.sqrt(math.fsum(x*x for x in z)/len(z))
    progress=project(data[-1]['after'],R)[0]-project(data[0]['before'],R)[0]
    original=not any(counts.values()) and progress>max(25.,.4*speed*len(data)*.05) and acquired>=20 and returned>=20
    result=dict(**{k:int(v) for k,v in counts.items()},ticks=len(data),progress_m=progress,
        acquired_intruder_ticks=int(acquired),recovered_leader_ticks=int(returned),original_gate_passed=bool(original),
        stable_return_2s_s=stable_time,stable_return_censored=stable_time is None,longest_correct_run_s=longest*.05,
        tail_spacing_rms_m=rms(tail),tail_spacing_max_abs_m=max(map(abs,tail)),tail_speed_rms_m_s=rms(relative),
        tail_correct_fraction=correct_tail/len(tail),tail_leader_cruise_rms_m_s=rms(headspeed),settling_delay_2s_s=settled_time)
    result['passed']=bool(original and stable_time is not None and settled_time is not None and exit_time+settled_time<=60.
        and result['tail_spacing_rms_m']<=2. and result['tail_spacing_max_abs_m']<=5. and result['tail_speed_rms_m_s']<=.5
        and result['tail_leader_cruise_rms_m_s']<=.5 and result['tail_correct_fraction']>=.95 and progress>.6*speed*len(data)*.05)
    return result


def compare(actual,stored):
    for k,v in actual.items():
        assert (close(v,stored[k]) if isinstance(v,float) else v==stored[k]),(k,v,stored.get(k))


def source_check(root):
    p=read(root/'plan.json')
    for name,expected in p['sources'].items():assert sha(root/'source'/name)==expected,('source',name)
    assert p['radio_range_m']==150.
    return p


def expected_accept(message,receiver,now,history):
    name=message['vehicle_id'];stamp=message['observed_s'];sequence=message['sequence']
    old=history.get((receiver,name))
    valid=name!=receiver and 0<=now-stamp<=.4+1e-9 and (old is None or sequence>old[0] and stamp>=old[1])
    if valid:history[(receiver,name)]=(sequence,stamp,message['state'])
    return valid


def independent_pace(history,own,now,R,speed):
    packet=history.get(('leader','follower'))
    if packet is None or not 0<=now-packet[1]<=.4+1e-9:return speed-4.,dict(pacing='member_unavailable',member_age_s=None,member_gap_m=None)
    _,stamp,z=packet;age=now-stamp;state=list(z)
    state[0]+=(z[3]*math.cos(z[2])-z[4]*math.sin(z[2]))*age
    state[1]+=(z[3]*math.sin(z[2])+z[4]*math.cos(z[2]))*age
    other=canonical(state,R);gap=canonical(own,R)[0]-other[0]
    goal=speed if gap<=60. else max(speed-4.,min(speed,other[2]+.3*(60.-gap)))
    return goal,dict(pacing='range_reserve' if goal<speed else 'cruise',member_age_s=age,member_gap_m=gap)


def check_python_episode(path,stored):
    spec=read(path/'case.json');data=rows(path/'ticks.jsonl');R=spec['profile']['radius'];speed=spec['speed']
    assert len(data)==1400 and sha(path/'ticks.jsonl')==stored['raw_sha256'] and sha(path/'case.json')==stored['case_sha256']
    history={};previous=None
    for i,row in enumerate(data):
        now=i*.05;assert row['tick']==i and row['time_s']==now
        if previous is not None:assert row['before']==previous
        for event in row['radio']:
            obj=json.loads(event['message']);stamp=obj['observed_s'];source=round(stamp/.05)
            origin=obj['vehicle_id'];actual=data[source]['before'] if origin=='follower' else data[source]['traffic_before'][origin]
            assert obj['state']==actual,'wire source state mismatch'
            assert event['received_s']==now
            assert expected_accept(obj,event['receiver'],now,history)==event['accepted'],'radio freshness/replay outcome'
        own=row['traffic_before']['leader'];goal,info=independent_pace(history,own,now,R,speed)
        saved=row['leader_pacing'];assert close(goal,saved['goal_speed'])
        for k,v in info.items():assert close(v,saved[k]) if isinstance(v,float) else v==saved[k]
        s,_,v=canonical(own,R);a=max(-2.5,min(2.5,.8*(goal-v)));nxt=max(speed-4.,min(speed,v+a*.05))
        ss=s+.025*(v+nxt);angle=ss/R if R else 0.
        expected=[R*math.sin(angle),R-R*math.cos(angle),angle,nxt,0.,nxt/R] if R else [ss,0.,0.,nxt,0.,0.]
        assert all(close(x,y) for x,y in zip(expected,row['traffic_after']['leader'])),'leader dynamics mismatch'
        assert close(a,saved['command_accel'])
        previous=row['after']
    compare(score(data,R,speed),stored)
    assert read(path/'replay.json')['passed'] and read(path/'summary.json')==stored
    return dict(ticks=len(data),passed=stored['passed'])


def check_native_episode(path,stored):
    spec=read(path/'config.json');R=spec['profile']['radius'];traces={n:rows(path/f'{n}.jsonl') for n in spec['starts']}
    provenance=read(path/'provenance.json')
    assert sha(path/'project/worlds/robust.wbt')==provenance['world_sha256']
    assert sha(path/'project/controllers/robust_vehicle/robust_vehicle.py')==provenance['controller_sha256']
    world=(path/'project/worlds/robust.wbt').read_text();script=(path/'project/controllers/robust_vehicle/robust_vehicle.py').read_text()
    assert world.count('range 150')==len(traces) and script.count('emitter.setRange(150.)')==1
    assert "pace_goal(node,state,now,road,speed)" in script
    history={};relays=0
    for name,data in traces.items():
        assert len(data)==1400 and sha(path/f'{name}.jsonl')==stored['raw_sha256'][name]
        assert sha(path/f'{name}-motion.jsonl')==stored['motion_sha256'][name]
        prior=0.;accepted=set();last_forward=float('-inf');setpoint=0.;emergency=False
        for i,row in enumerate(data):
            now=row['time_s'];assert close(now,(i+1)*.05)
            command=row['command'];assert -6.<=command['accel']<=2.5 and abs(command['steering'])<=.5+1e-9 and abs(command['steering']-prior)<=.03+1e-9
            prior=command['steering']
            native_cap=(min(16.,spec['speed']+8.) if name=='follower' else spec['speed']) if 'native_speed_cap' in script else spec['speed']+(8. if name=='follower' else 0.)
            if 'native_speed_cap' in script:
                assert row['native_speed_cap_m_s']==native_cap
                assert math.hypot(row['state'][3],row['state'][4])<=native_cap+.5
            if 'remaining_brake_ticks' in script:
                assert 'actuation' in row
                remaining=6 if command['accel']<=-6.+1e-9 else max(0,emergency-1)
                urgent=remaining>0
                if urgent:expected_target=0.
                else:
                    if emergency:setpoint=max(0.,row['state'][3])
                    if command['accel']<0:setpoint=min(setpoint,max(0.,row['state'][3]))
                    expected_target=max(0.,min(native_cap,setpoint+command['accel']*.05))
                assert row['actuation']==dict(setpoint_m_s=expected_target,brake_intensity=0.,
                    emergency=urgent,mode='motor_stop' if urgent else 'speed',remaining_brake_ticks=remaining)
                assert close(row['setpoint_m_s'],expected_target)
                assert row['applied_brake_intensity']==0.,'native velocity servo mixed with friction brake'
                assert row['applied_control_mode']==0
                assert close(row['applied_cruise_m_s'],expected_target) and row['applied_throttle'] is None
                setpoint=expected_target;emergency=remaining
            if 'native_braking_guard' in script:
                original=row['controller_command']
                assert original['steering']==command['steering'] and -6.<=original['accel']<=2.5
                if name=='follower':
                    ego_s,_,ego_v=canonical(row['state'],R);ego_v=max(0.,ego_v);threats=[]
                    for index,obj in enumerate(row['decision']['guard_objects']):
                        gap=obj['s']-ego_s-4.6
                        threshold=2.+.8*ego_v+max(0.,ego_v**2-max(0.,obj['speed'])**2)/5.
                        if obj['relevant'] and obj['s']>ego_s and gap<=threshold:
                            threats.append(dict(index=index,gap_m=gap,threshold_m=threshold))
                    guard=row['native_guard']
                    assert guard['active']==bool(threats) and guard['planning_braking_m_s2']==2.5 and guard['reaction_allowance_s']==.8
                    assert len(guard['objects'])==len(threats)
                    for actual,want in zip(guard['objects'],threats):
                        assert actual['index']==want['index'] and close(actual['gap_m'],want['gap_m']) and close(actual['threshold_m'],want['threshold_m'])
                    assert command['accel']==(-6. if threats else original['accel']),'native stopping reserve bypassed'
                else:assert row['native_guard'] is None and original==command
            p=row['pose']['position'];psi=row['pose']['rpy'][2];v=row['gps_velocity'];yaw=row['yaw_rate']
            expected=[p[0],p[1],psi,max(0.,v[0]*math.cos(psi)+v[1]*math.sin(psi)),-v[0]*math.sin(psi)+v[1]*math.cos(psi),yaw]
            assert all(close(x,y) for x,y in zip(expected,row['state']))
            for event in row['radio']:
                if event['kind']!='beacon':continue
                obj=json.loads(event['message'])
                assert expected_accept(obj,name,now,history)==event['accepted']
                if event['accepted']:accepted.add(event['message'])
            if name=='leader':
                goal,info=independent_pace(history,row['state'],now,R,spec['speed'])
                assert close(goal,row['decision']['npc_speed_m_s'])
                for k,v in info.items():assert close(v,row['decision'][k]) if isinstance(v,float) else v==row['decision'][k]
            forwarded=0
            for raw in row['transmitted']:
                assert name in spec['connected']
                obj=json.loads(raw)
                if obj.get('kind')=='range_scan':
                    assert obj['observer_id']==name and obj['scan']==row['generated_scan']['scan'];continue
                source=traces[obj['vehicle_id']][round(obj['observed_s']/.05)-1]
                assert source['state']==obj['state'] and source['time_s']==obj['observed_s']
                if obj['vehicle_id']!=name:
                    assert raw in accepted and -1e-9<=now-obj['observed_s']<=.25+1e-9
                    forwarded+=1;relays+=1
            assert forwarded<=1
            if forwarded:
                assert now-last_forward>=.1-1e-9,'forwarding exceeded one packet per100 ms'
                last_forward=now
    data=[]
    for i,row in enumerate(traces['follower']):
        traffic={n:v[i]['state'] for n,v in traces.items() if n!='follower'}
        data.append(dict(time_s=row['time_s'],before=row['state'],after=row['state'],traffic_before=traffic,
            traffic_after=traffic,command=row['command'],decision=row['decision']))
        for event in row['radio_incoming']:
            obj=json.loads(event['message'])
            if obj.get('kind')=='range_scan':
                source=traces[obj['observer_id']][round(obj['scan']['observed_s']/.05)-1]
                assert source['state']==obj['scan']['ego_state'] and source['generated_scan']['scan']==obj['scan']
            else:
                source=traces[obj['vehicle_id']][round(obj['observed_s']/.05)-1]
                assert source['state']==obj['state']
    compare(score(data,R,spec['speed'],True),stored)
    assert read(path/'verification.json')==stored
    return dict(passed=stored['passed'],samples=1400*len(traces),relays=relays)


def audit(root,stage='all',native=False):
    root=Path(root);plan=source_check(root);stages=('development','validation') if stage=='all' else (stage,)
    result={}
    for which in stages:
        summary=read(root/which/'summary.json');seeds=plan[which+'_seeds']
        speeds=plan[which+'_speeds'] if native else plan['speeds']
        expected=set(itertools.product(plan['cases'],speeds,seeds))
        assert len(summary['results'])==len(expected)
        assert {(z['case'],z['speed'],z['seed']) for z in summary['results']}==expected
        for stored in summary['results']:
            path=root/which/f"{stored['case']}-{stored['speed']:g}-{stored['seed']}"
            (check_native_episode if native else check_python_episode)(path,stored)
            assert stored['passed'],path.name
        assert summary['passed']
        result[which]=dict(passed=True,episodes=len(expected),tail_spacing_rms_max_m=max(z['tail_spacing_rms_m'] for z in summary['results']),
            tail_spacing_max_abs_m=max(z['tail_spacing_max_abs_m'] for z in summary['results']),
            settling_delay_max_s=max(z['settling_delay_2s_s'] for z in summary['results']),
            stable_return_censored=sum(z['stable_return_censored'] for z in summary['results']))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--stage',choices=('all','development','validation'),default='all');p.add_argument('--native',action='store_true')
    a=p.parse_args();print(json.dumps(audit(a.root,a.stage,a.native),indent=2))
