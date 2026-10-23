"""Deterministic open-loop interface validation; never imports primary models/PPO."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapter import VehicleAdapter
from vehicle import Driver


def audit(driver, config):
    node = driver.getSelf()
    physics = node.getField('physics').getSFNode()
    data = {
        'wheelbase_m': node.getField('wheelbase').getSFFloat(),
        'track_front_m': node.getField('trackFront').getSFFloat(),
        'track_rear_m': node.getField('trackRear').getSFFloat(),
        'chassis_mass_kg': physics.getField('mass').getSFFloat(),
        'chassis_com_m': physics.getField('centerOfMass').getMFVec3f(0),
        'chassis_inertia_kg_m2': sum((physics.getField('inertiaMatrix').getMFVec3f(i) for i in range(2)), []),
        'basic_time_step_ms': driver.getBasicTimeStep(),
        'wheels': {},
    }
    expected = config['expected_vehicle']
    for key in ('wheelbase_m', 'track_front_m', 'track_rear_m', 'chassis_mass_kg', 'chassis_com_m', 'chassis_inertia_kg_m2'):
        if data[key] != expected[key]:
            raise AssertionError(f'world/config mismatch: {key}: {data[key]} != {expected[key]}')
    for name in ('wheelFrontLeft', 'wheelFrontRight', 'wheelRearLeft', 'wheelRearRight'):
        wheel = node.getField(name).getSFNode()
        mass = wheel.getField('physics').getSFNode().getField('mass').getSFFloat()
        radius = wheel.getField('tireRadius').getSFFloat()
        assert mass == expected['wheel_mass_kg'] and radius == expected['wheel_radius_m']
        data['wheels'][name] = {'mass_kg': mass, 'radius_m': radius, 'initial_center_world_m': wheel.getBaseNodeField('endPoint').getSFNode().getPosition()}
    world = driver.getRoot().getField('children').getMFNode(0)
    contact = world.getField('contactProperties').getMFNode(0)
    data['friction'] = contact.getField('coulombFriction').getMFFloat(0)
    assert data['friction'] == expected['friction']
    assert math.isclose(data['basic_time_step_ms'] / 1000, config['control_period_s'])
    for field in ('suspensionFrontSpringConstant', 'suspensionRearSpringConstant',
                  'suspensionFrontDampingConstant', 'suspensionRearDampingConstant',
                  'wheelsDampingConstant', 'minSteeringAngle', 'maxSteeringAngle'):
        data[field] = node.getField(field).getSFFloat()
    for name, wheel in data['wheels'].items():
        target = [data['wheelbase_m'] if 'Front' in name else 0,
                  (1 if 'Left' in name else -1) * data['track_front_m'] / 2, 0.36]
        assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(wheel['initial_center_world_m'], target))
    data['total_mass_kg'] = data['chassis_mass_kg'] + sum(w['mass_kg'] for w in data['wheels'].values())
    data['world_sha256'] = hashlib.sha256((ROOT / 'worlds/vehicle_validation.wbt').read_bytes()).hexdigest()
    data['config_sha256'] = hashlib.sha256((ROOT / 'config.json').read_bytes()).hexdigest()
    return data


def main(driver):
    config = json.loads((ROOT / 'config.json').read_text())
    case = os.environ['LANS_WEBOTS_CASE']
    angle = config['cases'][case]
    out = Path(os.environ['LANS_WEBOTS_OUTPUT']).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{case}-vehicle.json').write_text(json.dumps(audit(driver, config), indent=2, allow_nan=False) + '\n')
    adapter = VehicleAdapter(driver, config['steering_limit_rad'])
    # Driver wheel-speed estimator differentiates sensor samples before stepping.
    # Two stationary steps establish finite readings; do not invent zeros.
    adapter.command(0.0, 0.0)
    for _ in range(2):
        if driver.step() == -1:
            raise RuntimeError('simulation stopped during sensor warmup')
    t_origin = driver.getTime()
    steps = round(config['duration_s'] / config['control_period_s'])
    with (out / f'{case}.csv').open('w', newline='') as stream:
        writer = None
        for index in range(steps):
            t = driver.getTime()
            requested = angle if t - t_origin >= config['steering_start_s'] - 1e-9 else 0.0
            speed = config['speed_m_s'] if t - t_origin >= config['motion_start_s'] - 1e-9 else 0.0
            applied = adapter.command(requested, speed)
            if driver.step() == -1:
                raise RuntimeError(f'simulation stopped early at step {index}')
            row = dict(step=index + 1, t_command_s=t, t_test_s=t - t_origin, steering_requested_rad=requested,
                       steering_applied_rad=applied, steering_webots_command_rad=-applied,
                       speed_target_m_s=speed, **adapter.state())
            if not all(math.isfinite(v) for v in row.values()):
                raise RuntimeError(f'nonfinite telemetry at step {index}')
            if writer is None:
                writer = csv.DictWriter(stream, fieldnames=row)
                writer.writeheader()
            writer.writerow(row)
    print(f'COMPLETE {case}: {steps} steps, {driver.getTime():.3f} simulation seconds', flush=True)


driver = Driver()
try:
    main(driver)
except Exception:
    traceback.print_exc()
    Path(os.environ['LANS_WEBOTS_OUTPUT'], 'failure.txt').write_text(traceback.format_exc())
    driver.simulationQuit(1)
else:
    driver.simulationQuit(0)
