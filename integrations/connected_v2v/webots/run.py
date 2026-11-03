"""Create a new isolated native convoy project and validate real radio delivery."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from integrations.connected_v2v.demo import digest, write
from .verify import verify

ROOT = Path(__file__).resolve().parents[3]


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output/'project'
    (project/'worlds').mkdir(parents=True)
    controller = project/'controllers/connected_vehicle'
    controller.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name('connected_vehicle.py'), controller/'connected_vehicle.py')
    runtime = ROOT/'integrations/webots/.runtime'
    # Reuse the existing generic Car parameters; no upstream or frozen file is edited.
    original = (ROOT/'integrations/webots/worlds/vehicle_validation.wbt').read_text()
    world, car = original.split('DEF VEHICLE Car {', 1)
    world = world.replace('../.runtime/protos/', str(runtime/'protos')+'/')
    world = world.replace('position 45 -55 60', 'position 20 -75 65')
    car = 'Car {'+car
    car = car.replace('controller "vehicle_validation"', 'controller "connected_vehicle"')
    car = car.replace('extensionSlot [', '''extensionSlot [
    GPS { name "v2v_gps" translation 1.4 0 0.4 }
    InertialUnit { name "v2v_imu" }
    Gyro { name "v2v_gyro" }
    Emitter { name "v2v_tx" channel 7 range 150 }
    Receiver { name "v2v_rx" channel 7 }''')
    for i, name in enumerate(['leader', 'follower-1', 'follower-2']):
        predecessor = ['', 'leader', 'follower-1'][i]
        instance = car.replace('translation 0 0 0.36', f'translation {-25*i} 0 0.36', 1)
        instance = instance.replace('name "lans-validation-surrogate"', f'name "{name}"\n  controllerArgs [ "{name}" "{predecessor}" ]')
        world += f'\nDEF CONNECTED_{i} '+instance
    target = project/'worlds/connected_convoy.wbt'
    target.write_text(world)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', choices=['nominal', 'peer_blackout'], default='nominal')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    runtime = ROOT/'integrations/webots/.runtime'
    if not (runtime/'webots/bin/webots-bin').is_file():
        parser.error('install the checksum-verified runtime with bash integrations/webots/install-private.sh')
    subprocess.run(['sha256sum', '-c', '../runtime-sha256.txt'], cwd=runtime, check=True)
    world = prepare(output)
    files = [*Path(__file__).parent.glob('*.py'), *Path(__file__).parent.parent.glob('*.py'),
             ROOT/'integrations/webots/worlds/vehicle_validation.wbt', ROOT/'integrations/webots/runtime-sha256.txt',
             ROOT/'integrations/unified_lans/traffic.py', ROOT/'integrations/unified_lans/physics.py',
             ROOT/'controllers/lqr_controller.py', ROOT/'models/bicycle_model.py']
    write(output/'provenance.json', dict(case=args.case, simulator='Webots R2025a generic Car', duration_s=12.,
                                        world_sha256=digest(world), sources={str(p.relative_to(ROOT)):digest(p) for p in files},
                                        clock='Webots simulation time; not a wall-clock deadline test',
                                        radio='native Emitter/Receiver, channel 7, range 150 m'))
    environment = os.environ.copy()
    environment.update(LANS_V2V_REPO=str(ROOT), LANS_V2V_NATIVE_OUTPUT=str(output),
                       LANS_V2V_NATIVE_CASE=args.case, LANS_V2V_NATIVE_SECONDS='12',
                       PATH='/workspace/lans-venv/bin:'+environment.get('PATH', ''),
                       OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    command = ['bash', str(ROOT/'integrations/webots/run-webots.sh'), '--batch', '--mode=fast',
               '--no-rendering', '--stdout', '--stderr', str(world)]
    with (output/'console.log').open('x') as log:
        subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                       timeout=120, check=True)
    result = verify(output)
    write(output/'verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
