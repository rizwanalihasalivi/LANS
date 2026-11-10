"""Runs once per native Webots Car; never reads another robot's supervisor truth."""
import json
import math
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(os.environ['LANS_V2V_REPO'])
sys.path.insert(0, str(ROOT))
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.platoon import FollowingConfig, PlatoonController
from integrations.unified_lans.run import clean
from vehicle import Driver


def main(driver):
    name, predecessor = sys.argv[1:3]
    predecessor = predecessor or None
    output = Path(os.environ['LANS_V2V_NATIVE_OUTPUT'])
    case = os.environ['LANS_V2V_NATIVE_CASE']
    duration = float(os.environ.get('LANS_V2V_NATIVE_SECONDS', '12'))
    endpoint = V2VEndpoint(name, expected_peers=[predecessor] if predecessor else ())
    follower = PlatoonController(endpoint, predecessor, following=FollowingConfig(cruise_speed_m_s=8.))
    gps, imu, gyro = [driver.getDevice(device) for device in ['v2v_gps', 'v2v_imu', 'v2v_gyro']]
    receiver, emitter = driver.getDevice('v2v_rx'), driver.getDevice('v2v_tx')
    for device in [gps, imu, gyro, receiver]:
        device.enable(50)
    emitter.setChannel(7); emitter.setRange(150.)
    receiver.setChannel(7)
    commanded_speed = 0.
    driver.setSteeringAngle(0.); driver.setCruisingSpeed(0.)
    count = 0; finished = False
    samples = fallbacks = received = muted = 0
    with (output/f'{name}.jsonl').open('x') as log, (output/f'{name}-receipts.jsonl').open('x') as receipts:
        while driver.step() != -1:
            # Physics is 10 ms; sensing/control is 50 ms, broadcasts are 100 ms.
            count += 1
            if count % 5:
                continue
            now = driver.getTime()
            if finished:
                if name == 'leader':
                    complete = all((output/f'{peer}-summary.json').exists()
                                   for peer in ['leader', 'follower-1', 'follower-2'])
                    if complete or now >= duration+1.:
                        driver.simulationQuit(0 if complete else 1)
                        return
                continue
            position = gps.getValues(); heading = imu.getRollPitchYaw()[2]
            speed = max(0., driver.getCurrentSpeed()/3.6)
            state = [position[0], position[1], heading, speed, 0., gyro.getValues()[2]]
            if not all(math.isfinite(v) for v in state):
                raise RuntimeError('native sensor initialization failed')
            endpoint.observe_local(state, now, now)
            while receiver.getQueueLength():
                payload = receiver.getBytes()
                accepted = endpoint.receive(payload, now)
                receipts.write(json.dumps(dict(received_s=now, message=payload.decode('utf-8', errors='surrogateescape'), accepted=accepted))+'\n')
                receiver.nextPacket(); received += 1
            if samples % 2 == 0:
                payload = endpoint.publish(state, now, now)
                if case == 'peer_blackout' and name == 'follower-1' and 5. <= now < 6.5:
                    muted += 1
                else:
                    emitter.send(payload)
            scheduled_brake = -2. if name == 'leader' and 7. <= now < 8. else None
            command, decision = follower.decide(now, leader_accel=scheduled_brake)
            commanded_speed = max(0., min(8., commanded_speed+command.accel*.05))
            driver.setCruisingSpeed(commanded_speed*3.6)
            # Existing native adapter convention: Webots steering is opposite SI-left.
            driver.setSteeringAngle(-command.steering)
            log.write(json.dumps(clean(dict(sample=samples, time_s=now, vehicle_id=name,
                                            state=state, command=dict(steering=command.steering, accel=command.accel),
                                            commanded_speed_m_s=commanded_speed, decision=decision,
                                            peers=endpoint.peers(now))), allow_nan=False)+'\n')
            log.flush(); receipts.flush()
            samples += 1
            fallbacks += decision['source'] in ('fallback_brake', 'hold_brake')
            if now >= duration-1e-8:
                summary = dict(vehicle_id=name, predecessor=predecessor, samples=samples,
                               received=received, accepted=endpoint.accepted, rejections=dict(endpoint.rejections),
                               fallback_samples=fallbacks, muted_broadcasts=muted,
                               final_peers=endpoint.peers(now), final_decision=decision,
                               scope='native Webots sensor/radio/driver integration, not PPO promotion')
                (output/f'{name}-summary.json').write_text(json.dumps(clean(summary), indent=2)+'\n')
                finished = True


if __name__ == '__main__':
    driver = Driver()
    try:
        main(driver)
    except Exception:
        traceback.print_exc()
        if sys.argv[1] == 'leader':
            driver.simulationQuit(1)
        raise
