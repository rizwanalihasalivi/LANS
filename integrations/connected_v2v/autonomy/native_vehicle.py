"""Native sensor adapter. The follower has no maneuver schedule or target IDs."""
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(os.environ.get('LANS_V2V_REPO', Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(ROOT))
from integrations.connected_v2v.autonomy.controller import AutonomousFollower, Detection, Scan
from integrations.connected_v2v.node import V2VEndpoint
from integrations.unified_lans.physics import Command, Config, baseline, constrain


def scan_from_native(sequence, now, state, targets):
    # Radar/GPS share x=1.4; native target box centre is x=1.3. Same declared
    # 0.1 m calibration as the frozen native recovery adapter, now with bearing.
    returns, complete = [], True
    for target in targets:
        if any(v is None or not math.isfinite(v) for v in target.values()):
            complete = False
            continue
        if not (.5 < target['distance'] < 119.8 and abs(target['azimuth']) <= .35):
            continue
        try:
            # Webots azimuth is clockwise; the SI vehicle frame is left-positive.
            returns.append(Detection(target['distance']+.1, -target['azimuth'], target['speed']))
        except ValueError:
            complete = False
    return Scan(sequence, now, tuple(state), tuple(returns), complete)


class OffsetRoad:
    def __init__(self, lateral):
        self.lateral = lateral

    def geometry(self, x):
        return self.lateral, 0., 0.


def local_state(position, heading, speed_vector, yaw_rate):
    c, s = math.cos(heading), math.sin(heading)
    return [position[0], position[1], heading,
            max(0., speed_vector[0]*c+speed_vector[1]*s),
            -speed_vector[0]*s+speed_vector[1]*c, yaw_rate]


def main(driver):
    name = sys.argv[1]
    output = Path(os.environ['LANS_AUTONOMY_NATIVE_OUTPUT'])
    case = os.environ['LANS_AUTONOMY_NATIVE_CASE']
    node = V2VEndpoint(name)
    follower = AutonomousFollower(node, speed=8.) if name == 'follower' else None
    gps, imu, gyro, radar, receiver, emitter = [driver.getDevice(n) for n in
        ('local_gps', 'local_imu', 'local_gyro', 'local_radar', 'local_rx', 'local_tx')]
    for device in (gps, imu, gyro, receiver):
        device.enable(50)
    radar.enable(100)
    receiver.setChannel(7)
    emitter.setChannel(7)
    emitter.setRange(150.)
    count = samples = scan_sequence = 0
    setpoint = 0.
    previous = Command()
    finished = False
    driver.setCruisingSpeed(0.)
    driver.setSteeringAngle(0.)
    with (output/f'{name}.jsonl').open('x') as log:
        while driver.step() != -1:
            count += 1
            if count % 5:
                continue
            now = driver.getTime()
            if finished:
                if name == 'leader':
                    complete = all((output/f'{n}-done.json').exists() for n in ('follower', 'leader', 'intruder'))
                    if complete or now >= 31.:
                        driver.simulationQuit(0 if complete else 1)
                        return
                continue
            position = gps.getValues()
            rpy = imu.getRollPitchYaw()
            state = local_state(position, rpy[2], gps.getSpeedVector(), gyro.getValues()[2])
            if not all(math.isfinite(v) for v in state):
                raise RuntimeError('invalid native local sensing')
            node.observe_local(state, now, now)
            receipts = []
            while receiver.getQueueLength():
                payload = receiver.getBytes()
                accepted = node.receive(payload, now)
                # JSON escapes surrogate bytes; malformed datagrams remain
                # losslessly replayable and cannot crash receipt logging.
                receipts.append(dict(message=payload.decode('utf-8', errors='surrogateescape'), accepted=accepted))
                receiver.nextPacket()
            if samples % 2 == 0:
                payload = node.publish(state, now, now)
                muted = (name == 'intruder' and case == 'nonconnected' or
                         name != 'follower' and case in ('v2v_blackout', 'dual_blackout') and 10. <= now < 11.5)
                if not muted:
                    emitter.send(payload)
            raw_targets = []
            scan = None
            accepted_scan = None
            if count % 10 == 0 and follower is not None:
                raw_targets = [dict(distance=t.distance, azimuth=t.azimuth, speed=t.speed) for t in radar.getTargets()]
                raw_targets = [{k:v if math.isfinite(v) else None for k,v in target.items()} for target in raw_targets]
                if not (case == 'dual_blackout' and 10. <= now < 11.5):
                    scan = scan_from_native(scan_sequence, now, state, raw_targets)
                    accepted_scan = follower.observe_scan(scan, now)
                scan_sequence += 1
            if follower is not None:
                command, info = follower.decide(now)
            else:
                # Only NPCs have scripted trajectories. They use their own GPS
                # and time, never set another vehicle's state or target.
                lateral = 0.
                if name == 'intruder':
                    lateral = 3.5 if now < 6. else max(0., 3.5*(8.-now)/2.) if now < 8. else (
                              0. if now < 16. else min(3.5, 3.5*(now-16.)/2.))
                speed = 7.5 if name == 'intruder' else 8.
                command = constrain(Command(baseline(state, OffsetRoad(lateral)), .8*(speed-state[3])), previous, Config())
                info = dict(npc_lateral_setpoint_m=lateral)
            cap = 16. if follower is not None else 8.
            setpoint = max(0., min(cap, setpoint+command.accel*.05))
            driver.setCruisingSpeed(setpoint*3.6)
            driver.setSteeringAngle(-command.steering)
            previous = command
            log.write(json.dumps(dict(sample=samples, time_s=now, state=state,
                native_pose=dict(position=list(position), rpy=rpy), radio=receipts,
                radar_targets=raw_targets, scan=asdict(scan) if scan else None, scan_accepted=accepted_scan,
                command=asdict(command), decision=info, setpoint_m_s=setpoint), allow_nan=False)+'\n')
            log.flush()
            samples += 1
            if now >= 30.-1e-8:
                (output/f'{name}-done.json').write_text(json.dumps(dict(samples=samples)))
                finished = True


if __name__ == '__main__':
    from vehicle import Driver
    main(Driver())
