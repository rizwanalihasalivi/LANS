from controller import Supervisor
from pathlib import Path
import json

robot = Supervisor()
box = robot.getFromDef('FALLING_BOX')
start_z = box.getPosition()[2]
camera = robot.getDevice('camera')
camera.enable(32)
for _ in range(100):
    if robot.step(32) == -1:
        raise RuntimeError('Simulation ended early')
end_z = box.getPosition()[2]
pixels = camera.getImage()
assert 0.05 < end_z < 0.2 and start_z > 0.9, (start_z, end_z)
assert pixels is not None and len(pixels) == 64 * 64 * 4
assert any(pixels[i] for i in range(len(pixels)) if i % 4 != 3)
assert camera.saveImage('/workspace/webots-setup/demo/camera.png', 100) == 0
result = {'steps': 100, 'simulation_seconds': robot.getTime(), 'start_z': start_z,
          'end_z': end_z, 'camera_bytes': len(pixels), 'passed': True}
Path('/workspace/webots-setup/demo/result.json').write_text(json.dumps(result, indent=2))
print('WEBOTS_SMOKE_PASS', json.dumps(result), flush=True)
robot.simulationQuit(0)
