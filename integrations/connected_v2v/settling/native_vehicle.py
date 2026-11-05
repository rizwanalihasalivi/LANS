"""Native adapter: actual anonymous Radar data, software misses/latency, native radio."""
from dataclasses import asdict
import heapq
import json
import math
import os
from pathlib import Path
import sys
import zlib
import numpy as np

ROOT=Path(os.environ.get('LANS_V2V_REPO',Path(__file__).resolve().parents[3]));sys.path.insert(0,str(ROOT))
from integrations.connected_v2v.autonomy.controller import Detection,Scan
from integrations.connected_v2v.settling.geometry import CircularRoad as Road,route_steering
from integrations.connected_v2v.autonomy.native_vehicle import local_state
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.settling.controller import SettlingFollower
from integrations.connected_v2v.settling.pacing import pace_goal
from integrations.connected_v2v.robustness.scenarios import maneuver,intruder_speed
from integrations.connected_v2v.settling.relay import FormationRelays as PendingRelays
from integrations.connected_v2v.robustness.perception import encode_peer_scan,is_peer_scan
from integrations.unified_lans.physics import Command,Config,baseline,constrain


def adapt_scan(sequence,now,state,targets,profile,rng):
    returns=[]
    for target in targets:
        if any(v is None or not math.isfinite(v) for v in target.values()):continue
        # Known ego bounding envelope: native radar can return the ego's own
        # body/wheels. This mask leaves a declared blind region, not clear road.
        # R2025a clamps azimuth to the +/-0.35 physical edge when only part of
        # a body is visible. That is not a center bearing. Keep the same0.33
        # central aperture as the Python sensor model; rejected fringe is
        # unavailable, never a complete/clear-road observation.
        if not 2.5<target['distance']<119.8 or abs(target['azimuth'])>.33:continue
        missed=rng.random()<profile['miss'] or profile['burst'] and 10.<=now<11.
        if missed:continue
        try:returns.append(Detection(target['distance']+.1,-target['azimuth'],target['speed']))
        except ValueError:pass
    rng.shuffle(returns)
    return Scan(sequence,now,tuple(state),tuple(returns),complete=False)


class OffsetRoad:
    def __init__(self,road,d):self.road,self.d=road,d
    def geometry(self,x):
        if not self.road.radius:return self.d,0.,0.
        radius=self.road.radius-self.d
        if abs(x)>=.9*radius:raise ValueError('outside declared native curve fixture')
        return self.road.radius-math.sqrt(radius**2-x*x),math.asin(x/radius),1./radius


def native_braking_guard(command,info,state,road):
    """Native stopping reserve uses the measured plant, not requested -6.

    The unchanged Car velocity-motor ramp realizes about2.78m/s2 braking.
    Plan with2.5 and0.8s allowance, using only fresh observed guard objects.
    """
    ego_s,_,speed,_=road.canonical(state);speed=max(0.,speed)
    objects=[]
    for index,obj in enumerate(info['guard_objects']):
        gap=obj['s']-ego_s-4.6
        threshold=2.+.8*speed+max(0.,speed**2-max(0.,obj['speed'])**2)/5.
        if obj['relevant'] and obj['s']>ego_s and gap<=threshold:
            objects.append(dict(index=index,gap_m=float(gap),threshold_m=float(threshold)))
    active=bool(objects)
    return (Command(command.steering,-6.) if active else command),dict(active=active,
        planning_braking_m_s2=2.5,reaction_allowance_s=.8,objects=objects)


def native_speed_cap(cruise,follower):
    return min(16.,cruise+8.) if follower else cruise


def native_actuation(setpoint,measured_speed,acceleration,cap,brake_ticks):
    """Map maximum requests to the unchanged stable SPEED-mode motor stop.

    Its realized ramp is about2.78m/s2, not requested -6. The native reserve
    plans with2.5; actual response is qualified from motion logs. Mixing locked
    friction brakes with the strong velocity servo destabilized earlier probes.
    """
    remaining=6 if acceleration<=-6.+1e-9 else max(0,brake_ticks-1)
    emergency=remaining>0
    if emergency:
        return dict(setpoint_m_s=0.,brake_intensity=0.,emergency=True,
            mode='motor_stop',remaining_brake_ticks=remaining)
    if brake_ticks:setpoint=max(0.,measured_speed)
    if acceleration<0:setpoint=min(setpoint,max(0.,measured_speed))
    return dict(setpoint_m_s=max(0.,min(cap,setpoint+acceleration*.05)),
        brake_intensity=0.,emergency=False,mode='speed',remaining_brake_ticks=0)


def main(driver):
    name=sys.argv[1];output=Path(os.environ['LANS_ROBUST_OUTPUT'])
    config=json.loads((output/'config.json').read_text());p=config['profile'];speed=config['speed'];seed=config['seed']
    road=Road(p['radius']);node=V2VEndpoint(name)
    follower=SettlingFollower(node,road=road,speed=speed) if name=='follower' else None
    gps,imu,gyro,radar,receiver,emitter=[driver.getDevice(n) for n in ('local_gps','local_imu','local_gyro','local_radar','local_rx','local_tx')]
    for d in (gps,imu,gyro,receiver):d.enable(10)
    radar.enable(100);receiver.setChannel(7);emitter.setChannel(7);emitter.setRange(150.)
    key=zlib.crc32(name.encode())
    rng=np.random.default_rng(np.random.SeedSequence([seed,11,key]))
    latency_rng=np.random.default_rng(np.random.SeedSequence([seed,13,key]))
    radio_rng=np.random.default_rng(np.random.SeedSequence([seed,23,key]))
    radio_queue=[];radar_queue=[];serial=0;sample=0;count=0;setpoint=0.;previous=Command();finished=False
    brake_ticks=0
    pending=PendingRelays()
    driver.setCruisingSpeed(0.);driver.setBrakeIntensity(0.);driver.setSteeringAngle(0.)
    with (output/f'{name}.jsonl').open('x') as log, (output/f'{name}-motion.jsonl').open('x') as motion:
        while driver.step()!=-1:
            count+=1
            mp=gps.getValues();mr=imu.getRollPitchYaw();mv=gps.getSpeedVector();my=gyro.getValues()[2]
            motion.write(json.dumps(dict(time_s=driver.getTime(),position=list(mp),heading=mr[2],
                velocity=list(mv),yaw_rate=my),allow_nan=False)+'\n')
            if count%5:continue
            now=driver.getTime()
            if finished:
                if name=='leader':
                    complete=all((output/f'{n}-done.json').exists() for n in config['starts'])
                    if complete or now>=config['seconds']+1.:
                        driver.simulationQuit(0 if complete else 1);return
                continue
            position=gps.getValues();rpy=imu.getRollPitchYaw();vector=gps.getSpeedVector();yaw=gyro.getValues()[2]
            state=local_state(position,rpy[2],vector,yaw)
            if not all(math.isfinite(v) for v in state):raise RuntimeError('invalid native local sensing')
            node.observe_local(state,now,now)
            incoming=[];radio=[];transmitted=[]
            while receiver.getQueueLength():
                payload=receiver.getBytes();receiver.nextPacket()
                if radio_rng.random()<.1:continue
                copies=2 if radio_rng.random()<.1 else 1
                for _ in range(copies):
                    due=now+max(0.,.05+float(radio_rng.uniform(-.025,.025)));serial+=1
                    heapq.heappush(radio_queue,(due,serial,payload))
                    incoming.append(dict(serial=serial,due_s=due,message=payload.decode('utf-8',errors='surrogateescape')))
            while radio_queue and radio_queue[0][0]<=now+1e-9:
                due,event,payload=heapq.heappop(radio_queue)
                kind='range_scan' if is_peer_scan(payload) else 'beacon'
                accepted=(follower.observe_peer_scan(payload,now) if follower is not None else False) if kind=='range_scan' else node.receive(payload,now)
                radio.append(dict(serial=event,message=payload.decode('utf-8',errors='surrogateescape'),accepted=accepted,kind=kind))
                if accepted and kind=='beacon':pending.add(payload)
            if sample%2==0 and (name=='follower' or name in config['connected']):
                payload=node.publish(state,now,now)
                forwarded=pending.take(now,road)
                if not(p['radio_blackout'] and name!='follower' and 11.<=now<12.5):
                    emitter.send(payload)
                    transmitted.append(payload.decode())
                    if forwarded is not None:
                        emitter.send(forwarded);transmitted.append(forwarded.decode())
            raw=[];generated=None;radar_events=[]
            if count%10==0 and (follower is not None or name in config['connected']):
                raw=[dict(distance=t.distance,azimuth=t.azimuth,speed=t.speed) for t in radar.getTargets()]
                raw=[{k:v if math.isfinite(v) else None for k,v in t.items()} for t in raw]
                if not(follower is not None and p['radar_blackout'] and 11.<=now<12.5):
                    scan=adapt_scan(count//10-1,now,state,raw,p,rng)
                    if follower is not None:
                        due=now+p['latency']+float(latency_rng.uniform(-p['latency_jitter'],p['latency_jitter']))
                        heapq.heappush(radar_queue,(due,scan.sequence,scan));generated=dict(scan=asdict(scan),due_s=due)
                    else:
                        generated=dict(scan=asdict(scan),due_s=now)
                        if not(p['radio_blackout'] and 11.<=now<12.5):
                            payload=encode_peer_scan(name,scan);emitter.send(payload);transmitted.append(payload.decode())
            while radar_queue and radar_queue[0][0]<=now+1e-9:
                _,_,scan=heapq.heappop(radar_queue)
                radar_events.append(dict(scan=asdict(scan),accepted=follower.observe_scan(scan,now)))
            if follower is not None:command,info=follower.decide(now)
            else:
                d=3.5 if name.startswith('adjacent') else 0.
                goal=speed-2.*min(1.,max(0.,now-18.)) if name in ('adjacent-0','adjacent-1') else speed
                if name=='intruder':d,_=maneuver(now,native=True);goal=intruder_speed(now,speed,p['brake'])
                if road.radius:goal*=1-d/road.radius
                pace_info={}
                if name=='leader':goal,pace_info=pace_goal(node,state,now,road,speed)
                command=constrain(Command(route_steering(state,road,d),.8*(goal-state[3])),previous,Config())
                info=dict(npc_offset_m=d,npc_speed_m_s=goal,**pace_info)
            controller_command=command;native_guard=None
            if follower is not None:command,native_guard=native_braking_guard(command,info,state,road)
            cap=native_speed_cap(speed,follower is not None)
            actuation=native_actuation(setpoint,state[3],command.accel,cap,brake_ticks)
            setpoint=actuation['setpoint_m_s'];brake_ticks=actuation['remaining_brake_ticks'];previous=command
            driver.setCruisingSpeed(setpoint*3.6)
            driver.setBrakeIntensity(actuation['brake_intensity'])
            driver.setSteeringAngle(-command.steering)
            applied_brake=driver.getBrakeIntensity();applied_mode=driver.getControlMode()
            applied_cruise=driver.getTargetCruisingSpeed()/3.6
            applied_throttle=None
            log.write(json.dumps(dict(sample=sample,time_s=now,state=state,gps_velocity=list(vector),yaw_rate=yaw,
                pose=dict(position=list(position),rpy=rpy),radio_incoming=incoming,radio=radio,radar_targets=raw,
                transmitted=transmitted,
                generated_scan=generated,radar=radar_events,command=asdict(command),decision=info,setpoint_m_s=setpoint,
                actuation=actuation,applied_brake_intensity=applied_brake,applied_cruise_m_s=applied_cruise,
                applied_control_mode=applied_mode,applied_throttle=applied_throttle,
                controller_command=asdict(controller_command),native_guard=native_guard,
                native_speed_cap_m_s=cap),allow_nan=False)+'\n')
            log.flush();motion.flush();sample+=1
            if now>=config['seconds']-1e-8:
                (output/f'{name}-done.json').write_text(json.dumps(dict(samples=sample)));finished=True


if __name__=='__main__':
    from vehicle import Driver
    main(Driver())
