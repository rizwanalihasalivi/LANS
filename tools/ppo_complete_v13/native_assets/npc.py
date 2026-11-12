"""Independent physical traffic car; pose is not written by this controller."""
import json,math,os
from pathlib import Path
import numpy as np

if __name__=='__main__':
    from vehicle import Driver
    from tools.ppo_complete_v13.native_adapter import body_state
    from tools.unified_campaign.study import StudyRoute
    from tools.unified_control_v4.control import ScheduledLQR
    d=Driver();case=json.loads(Path(os.environ['LANS_NATIVE_CASE']).read_text());name=d.getName()
    initial=np.asarray(case['initial_npcs'][name]);target=float(initial[3]);node=d.getSelf();dt=d.getBasicTimeStep()/1000
    d.setBrakeIntensity(0.);d.setCruisingSpeed(target*3.6);d.setSteeringAngle(0.)
    for motorname in ('left_steer','right_steer'):
        motor=d.getDevice(motorname);motor.setControlPID(1/dt,0,0);motor.setVelocity(.6)
    metadata=None;steer=0.;tick=0;route=StudyRoute(case['route_kind'],case['mirror'],case['phase'],case['amplitude'])
    baseline=ScheduledLQR(16.);baseline.stiffness=1.
    while d.step()!=-1:
        if metadata is None:
            path=Path(case['output'])/'initialization.json'
            if path.exists():metadata=json.loads(path.read_text())
            else:continue
        frame=metadata['frame'];angle=frame['angle_rad'];c,s=math.cos(angle),math.sin(angle)
        rotation=np.array([[c,-s],[s,c]]);state=body_state(node)
        state[:2]=rotation@(state[:2]-np.asarray(frame['origin_world_cg_m']))+np.asarray(frame['offset_map_m'])
        state[2]=math.atan2(math.sin(state[2]+angle),math.cos(state[2]+angle))
        if case['scenario']=='curved':desired=baseline(state,route)
        else:
            heading=float(initial[2]);normal=np.array([-math.sin(heading),math.cos(heading)])
            lateral=float(normal@(state[:2]-initial[:2]));err=math.atan2(math.sin(state[2]-heading),math.cos(state[2]-heading))
            desired=float(np.clip(-.12*lateral-.6*err,-.5,.5))
        steer=float(np.clip(desired,steer-.6*dt,steer+.6*dt));d.setSteeringAngle(-steer)
        tick+=1
