"""Private native driver for a selected nonlearned balanced gate; no policy load."""
import csv
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(os.environ.get('LANS_INTEGRATION_ROOT', Path(__file__).resolve().parents[2]))
RESEARCH = ROOT / 'research'
sys.path.insert(0, str(RESEARCH / 'revision13'))
sys.path.insert(0, str(RESEARCH / 'revision8'))
import bootstrap
import numpy as np
from comparison import configure_lqr
from core import GAINS
from kernels import initial_executor, lqr
from dynamics13 import measure13, path_values13
from gate13 import execution_step13
from native13 import candidate_name, summarize_records


def vehicle_audit(node, dt):
    physics=node.getField('physics').getSFNode()
    mass=physics.getField('mass').getSFFloat()
    cg=physics.getField('centerOfMass').getMFVec3f(0)[0]
    inertia=physics.getField('inertiaMatrix').getMFVec3f(0)[2]
    total_mass=mass;moment=mass*cg;wheels=[]
    for name in ('wheelFrontLeft','wheelFrontRight','wheelRearLeft','wheelRearRight'):
        wheel=node.getField(name).getSFNode();wp=wheel.getField('physics').getSFNode()
        wm=wp.getField('mass').getSFFloat();wi=wp.getField('inertiaMatrix').getMFVec3f(0)[2]
        pos=wheel.getBaseNodeField('endPoint').getSFNode().getPosition()
        total_mass+=wm;moment+=wm*pos[0];wheels.append((wm,wi,pos))
    total_cg=moment/total_mass
    total_inertia=inertia+mass*(cg-total_cg)**2+sum(wi+wm*((pos[0]-total_cg)**2+pos[1]**2) for wm,wi,pos in wheels)
    assert abs(total_mass-1650)<1e-8 and abs(total_cg-1.4)<1e-8 and abs(total_inertia-4224)<1e-7
    return dict(mass_kg=total_mass,nominal_cg_x_m=total_cg,nominal_yaw_inertia=total_inertia,
                physics_step_s=dt,controller_period_s=.01)


def main(driver):
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text())
    candidate_name({'variant':case['variant'],'residual_rad':case['residual_rad']})
    assert case['mode'] in ('lqr','selected') and case['service_ticks'] in (0,10)
    configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)])
    out=Path(case['output']);out.mkdir(parents=True,exist_ok=True)
    node=driver.getSelf();dt=driver.getBasicTimeStep()/1000
    assert math.isclose(dt,.001)
    physics_steps=round(.01/dt)
    left=driver.getDevice('left_steer_sensor');right=driver.getDevice('right_steer_sensor')
    left.enable(round(dt*1000));right.enable(round(dt*1000))
    for motor in ('left_steer','right_steer'):driver.getDevice(motor).setControlPID(1/dt,0,0)
    (out/'vehicle.json').write_text(json.dumps(vehicle_audit(node,dt),indent=2)+'\n')
    speed=float(case['speed']);path=(1.,0.,0.,0.,1.,float(case['path_sign']))
    # Compile every runtime layout before acceleration/testing; no gate state survives warmup.
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4)
    state0=np.zeros(6);noise0=np.zeros(4)
    _,_,_,measured,k=measure13(state0,speed,path,noise0,0,estimate,cov,previous,True,1.)
    baseline,gain=lqr(estimate,measured,k,gains)
    execution_step13(initial_executor(),0.,case['residual_rad'],case['service_ticks'],baseline,
                     estimate,0.,measured,k,gain,case['variant'])
    def state():
        pos=node.getPosition();rot=node.getOrientation();vel=node.getVelocity()
        psi=math.atan2(rot[3],rot[0]);longitudinal=vel[0]*math.cos(psi)+vel[1]*math.sin(psi)
        lateral=-vel[0]*math.sin(psi)+vel[1]*math.cos(psi)
        return np.array([pos[0]+1.4*math.cos(psi),pos[1]+1.4*math.sin(psi),psi,lateral,vel[5],
                         -(left.getValue()+right.getValue())/2]),longitudinal
    driver.setSteeringAngle(0.);driver.setCruisingSpeed(speed*3.6)
    for _ in range(round(10/dt)):
        if driver.step()==-1:raise RuntimeError('stopped during warmup')
    initial,initial_speed=state();x_origin=initial[0];t_origin=driver.getTime()
    (out/'initial-state.json').write_text(json.dumps(dict(state_cg=initial.tolist(),speed_m_s=initial_speed,
        simulation_time_s=t_origin,explicit_actuator_rad=0.,measured_wheel_angle_rad=float(initial[5]),
        lateral_offset_m=float(initial[1]-path_values13(0.,path)[0]),no_teleport=True),indent=2)+'\n')
    scheduled=round(case['duration']/.01)
    noise=np.random.default_rng(case['seed']).normal(0,np.array([.03,math.radians(.17),.01,.1])*case['noise'],(scheduled,4))
    noise[:,:3]*=case['path_sign']
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4);worker=initial_executor()
    actuator=0.;records=[];failure=None
    with (out/'telemetry.csv').open('w',newline='') as stream:
        writer=None
        for tick in range(scheduled):
            t=driver.getTime();s,v=state();s[0]-=x_origin
            estimate,cov,previous,measured,k=measure13(s,v if v>5 else speed,path,noise[tick],0,
                estimate,cov,previous,tick==0,float(case['noise']))
            baseline,gain=lqr(estimate,measured,k,gains)
            started=time.perf_counter()
            if case['mode']=='lqr':command,weight,reason,submitted=baseline,0.,10,False
            else:
                command,weight,reason,submitted=execution_step13(worker,tick*.01,case['residual_rad'],
                    case['service_ticks'],baseline,estimate,s[5],measured,k,gain,case['variant'])
            gate_wall=time.perf_counter()-started
            if case['service_ticks']==10:assert command==baseline and weight==0.
            if not math.isfinite(command):raise RuntimeError('nonfinite native command')
            before=actuator;wheel_before=s[5]
            for _ in range(physics_steps):
                actuator=float(np.clip(actuator+dt*np.clip((command-actuator)/.05,-.35,.35),-.5,.5))
                driver.setSteeringAngle(-actuator);driver.setCruisingSpeed(speed*3.6)
                if driver.step()==-1:raise RuntimeError('unexpected simulator stop')
            post,post_speed=state();post[0]-=x_origin
            ref_y,ref_heading,_=path_values13(post[0],path)
            row=dict(step=tick+1,t_command_s=t,t_state_s=driver.getTime(),t_test_s=tick*.01,
                command_rad=command,lqr_command_rad=baseline,actuator_rad=actuator,
                actuator_increment_rad=actuator-before,actuator_rate_rad_s=(actuator-before)/.01,
                pre_measured_center_angle_rad=wheel_before,measured_center_angle_rad=post[5],
                measured_wheel_increment_rad=post[5]-wheel_before,measured_wheel_rate_rad_s=(post[5]-wheel_before)/.01,
                speed_target_m_s=speed,speed_truth_m_s=post_speed,x_cg_m=post[0],y_cg_m=post[1],
                heading_rad=post[2],vy_truth_m_s=post[3],yaw_rate_rad_s=post[4],reference_y_m=ref_y,
                reference_heading_rad=ref_heading,error_m=post[1]-ref_y,heading_error_rad=post[2]-ref_heading,
                estimated_error_m=estimate[0],estimated_vy_m_s=estimate[1],estimated_heading_error_rad=estimate[2],
                estimated_yaw_rate_rad_s=estimate[3],measured_speed_input_m_s=measured,
                curvature_input_per_m=k,
                weight=weight,reason=reason,submitted=int(submitted),packet_sequence=worker[3],
                packet_available=int(worker[3]>=0),packet_observed_s=worker[4] if worker[3]>=0 else 0.,
                packet_age_s=tick*.01-worker[4] if worker[3]>=0 else 0.,pending_sequence=worker[7],
                gate_wall_s=gate_wall)
            if not all(math.isfinite(value) for value in row.values()):raise RuntimeError('nonfinite native telemetry')
            if writer is None:writer=csv.DictWriter(stream,fieldnames=row,lineterminator='\n');writer.writeheader()
            writer.writerow(row);records.append(row)
            if abs(row['error_m'])>2.5 or abs(row['heading_error_rad'])>.6:failure='tracking_envelope';break
    metrics=summarize_records(records,case,failure)
    assert metrics['max_actuator_rate_rad_s']<=.35000001
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')


if __name__ == '__main__':
    from vehicle import Driver
    driver=Driver()
    try:main(driver)
    except Exception:
        Path(os.environ['LANS_CASE_CONFIG']).with_suffix('.failure.txt').write_text(traceback.format_exc())
        traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)
