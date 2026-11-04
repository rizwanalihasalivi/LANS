"""Build a physical two-lane road ribbon, with native Cars and painted boundaries."""
from pathlib import Path
import shutil
import numpy as np
from integrations.connected_v2v.autonomy.study import ROOT
from integrations.connected_v2v.autonomy.road import Road


def mesh(road,lo,hi,z=0.,thickness=False):
    points=[];faces=[]
    samples=np.linspace(-150.,1500.,331)
    for s in samples:
        for d,height in ((lo,z),(hi,z),(lo,z-.2),(hi,z-.2)) if thickness else ((lo,z),(hi,z)):
            x,y=road.position(s,d);points.append(f'{x:.9f} {y:.9f} {height:.5f}')
    stride=4 if thickness else 2
    for i in range(len(samples)-1):
        a,b=stride*i,stride*(i+1)
        faces.append(f'{a} {b} {b+1} {a+1} -1')
        if thickness:
            faces.extend([f'{a+2} {a+3} {b+3} {b+2} -1',f'{a} {a+2} {b+2} {b} -1',
                          f'{a+1} {b+1} {b+3} {a+3} -1'])
    if thickness:
        end=stride*(len(samples)-1)
        faces.extend(['0 1 3 2 -1',f'{end} {end+2} {end+3} {end+1} -1'])
    return 'IndexedFaceSet { coord Coordinate { point [ '+', '.join(points)+' ] } coordIndex [ '+', '.join(faces)+' ] }'


def prepare(output,config):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    directory=output/'project/controllers/robust_vehicle';directory.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name('native_vehicle.py'),directory/'robust_vehicle.py')
    original=(ROOT/'integrations/webots/worlds/vehicle_validation.wbt').read_text()
    world,car=original.split('DEF VEHICLE Car {',1)
    world=world[:world.index('DEF ROAD Solid {')]
    world=world.replace('../.runtime/protos/',str(ROOT/'integrations/webots/.runtime/protos')+'/')
    world=world.replace('randomSeed 42',f"randomSeed {config['seed']}")
    road=Road(config['profile']['radius'])
    world+='Solid { contactMaterial "road" children [ Shape { appearance PBRAppearance { baseColor .24 .24 .24 roughness 1 metalness 0 } geometry DEF ROAD_MESH '+mesh(road,-2.5,6.,thickness=True)+' } ] boundingObject USE ROAD_MESH }\n'
    for d in (-1.75,1.75,5.25):
        world+='Shape { appearance PBRAppearance { baseColor 1 1 .8 roughness 1 metalness 0 } geometry '+mesh(road,d-.035,d+.035,z=.002)+' }\n'
    car='Car {'+car
    car=car.replace('controller "vehicle_validation"','controller "robust_vehicle"')
    p=config['profile']
    car=car.replace('extensionSlot [',f'''extensionSlot [
    GPS {{ name "local_gps" translation 1.4 0 0.4 }}
    InertialUnit {{ name "local_imu" }}
    Gyro {{ name "local_gyro" }}
    Emitter {{ name "local_tx" channel 7 range 150 }}
    Receiver {{ name "local_rx" channel 7 }}
    Radar {{ name "local_radar" translation 1.4 0 0.4 minRange 0.5 maxRange 120 horizontalFieldOfView 0.7 verticalFieldOfView 0.4 minRadialSpeed 0 maxRadialSpeed 0 rangeNoise {p['range_noise']} speedNoise {p['rate_noise']} angularNoise {p['bearing_noise']} occlusion TRUE }}''')
    for name,start in config['starts'].items():
        s,d=start;x,y=road.position(s,d);heading=s/road.radius if road.radius else 0.
        instance=car.replace('translation 0 0 0.36',f'translation {x} {y} 0.36\n rotation 0 0 1 {heading}',1)
        instance=instance.replace('name "lans-validation-surrogate"',f'name "{name}"\n controllerArgs [ "{name}" ]')
        world+='\n'+instance
    target=output/'project/worlds/robust.wbt';target.parent.mkdir();target.write_text(world)
    return target
