from contextlib import ExitStack
import csv,json,math,os,sys,traceback,time
from pathlib import Path
import numpy as np
ROOT=Path(os.environ['LANS_INTEGRATION_ROOT'])
sys.path.insert(0,str(ROOT/'research'))
from core import Sensor,lqr,path_values,Supervisor,GAINS
sys.path.insert(0,str(ROOT/'research/revision2'))
from gating import Gate,predict_cost
from vehicle import Driver
from comparison import configure_lqr
from worker import PolicyWorker
from causal_runtime import FastSensor,CausalWorker,actor_observation,packet_ages
from kernels import lqr as compiled_lqr

def main(d):
    with ExitStack() as cleanup:
        return _main(d,cleanup)

def _main(d,cleanup):
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text())
    configure_lqr()
    out=Path(case['output']);out.mkdir(parents=True,exist_ok=True)
    node=d.getSelf();dt=d.getBasicTimeStep()/1000
    left=d.getDevice('left_steer_sensor');right=d.getDevice('right_steer_sensor')
    left.enable(round(dt*1000));right.enable(round(dt*1000))
    # Track the explicitly simulated actuator; avoid adding the default ~0.1s servo lag.
    for motor_name in ('left_steer','right_steer'):
        d.getDevice(motor_name).setControlPID(1/dt,0,0)
    # Verify the nominal composite calibration from actual runtime Physics fields.
    p=node.getField('physics').getSFNode();mass=p.getField('mass').getSFFloat()
    cg=p.getField('centerOfMass').getMFVec3f(0)[0];izz=p.getField('inertiaMatrix').getMFVec3f(0)[2]
    whole_mass=mass;moment=mass*cg;wheels=[]
    for name in ('wheelFrontLeft','wheelFrontRight','wheelRearLeft','wheelRearRight'):
        w=node.getField(name).getSFNode();wp=w.getField('physics').getSFNode()
        wm=wp.getField('mass').getSFFloat();wi=wp.getField('inertiaMatrix').getMFVec3f(0)[2]
        pos=w.getBaseNodeField('endPoint').getSFNode().getPosition()
        whole_mass+=wm;moment+=wm*pos[0];wheels.append((wm,wi,pos))
    whole_cg=moment/whole_mass
    whole_izz=izz+mass*(cg-whole_cg)**2+sum(wi+wm*((pos[0]-whole_cg)**2+pos[1]**2) for wm,wi,pos in wheels)
    assert abs(whole_mass-1650)<1e-8 and abs(whole_cg-1.4)<1e-8 and abs(whole_izz-4224)<1e-7
    (out/'vehicle.json').write_text(json.dumps({'mass_kg':whole_mass,'nominal_cg_x_m':whole_cg,'nominal_yaw_inertia':whole_izz,'physics_step_s':dt,'controller_period_s':.01},indent=2)+'\n')
    sensor=FastSensor(case.get('seed',9000),case.get('noise',0),case.get('sensor_delay_steps',0))
    mode=case['mode'];speed=case['speed'];actuator=0.;steps=round(.01/dt)
    assert math.isclose(steps*dt,.01)
    policy=None;worker=None;packet_meta=None
    if mode in ('causal_student',):
        worker=CausalWorker(case['policy'],case.get('delay_ms',0)/1000)
        cleanup.callback(worker.close)
    gate=Gate(case['gate_config']);output=None;pending=None;sequence=0;model_inference_wall=0.
    gains=np.array([GAINS[v] for v in (15,20,25)]);last_command=0.;packet_log=[]
    # Warm compilation before physical warmup, without mutating the gate.
    predict_cost(np.zeros(4),0.,0.,float(speed),0.,GAINS[speed],case['gate_config']['horizon_steps'])
    def state():
        pos=node.getPosition();rot=node.getOrientation();vel=node.getVelocity()
        psi=math.atan2(rot[3],rot[0]);v=vel[0]*math.cos(psi)+vel[1]*math.sin(psi)
        vy=-vel[0]*math.sin(psi)+vel[1]*math.cos(psi)
        return np.array([pos[0]+1.4*math.cos(psi),pos[1]+1.4*math.sin(psi),psi,vy,vel[5],-(left.getValue()+right.getValue())/2]),v
    d.setSteeringAngle(0);d.setCruisingSpeed(speed*3.6)
    # Physical acceleration/settling, never teleport the moving car into its test trajectory.
    for _ in range(round(10/dt)):
        if d.step()==-1:raise RuntimeError('stopped during warmup')
    initial,_=state();x_origin=initial[0];t_origin=d.getTime()
    path=tuple(float(v) for v in case['path_parameters'])
    # Warm the optimized estimator and every returned-array layout using a throwaway sensor.
    warm_sensor=FastSensor(0,case.get('noise',0),case.get('sensor_delay_steps',0))
    for _ in range(40):
        physical,est,k,v=warm_sensor.measure(initial,float(speed),path)
        b,g=compiled_lqr(est,v,k,gains)
        predict_cost(est,0.,b,v,k,g,20)
    wall_origin=time.perf_counter_ns()
    records=[];failure=None
    with (out/'telemetry.csv').open('w',newline='') as stream:
        writer=None
        for i in range(round(case.get('duration',12)/.01)):
            release_ns=time.perf_counter_ns();deadline_ns=wall_origin+i*10_000_000+10_000_000
            t=d.getTime();s,v=state();s[0]-=x_origin
            physical,estimate,kappa,measured_v=sensor.measure(s,v if v>5 else speed,path)
            baseline,gain=compiled_lqr(estimate,measured_v,kappa,gains);weight=0.;reason='open_loop'
            wall_age=sim_age=effective_age=0.;inference_observed_ns=0
            age=0.;available=0;j0=j1=math.nan;gate_wall=0.
            if mode=='open':command=case.get('angle',0) if i>=200 else 0.
            else:
                command=baseline;reason='lqr'
                if mode in ('causal_student',):
                    received=worker.poll()
                    if received is not None:
                        packet_meta=received;packet_log.append(received.copy())
                        model_inference_wall=(received['inferred_ns']-received['entered_ns'])/1e9
                    if worker.failed:packet_meta=None
                    if packet_meta is not None:
                        sim_age,wall_age,effective_age=packet_ages(packet_meta,t,time.perf_counter_ns())
                        output=(packet_meta['seq'],t-effective_age,packet_meta['residual'])
                        inference_observed_ns=packet_meta['observed_ns']
                    else:output=None
                    obs=actor_observation(physical,gate,packet_meta,effective_age,last_command)
                    worker.submit(obs,release_ns,t)
                    age=effective_age;available=int(packet_meta is not None)
                    started=time.perf_counter()
                    command,weight,reason,j0,j1=gate.choose(t,baseline,output,estimate,s[5],measured_v,kappa,gain,'residual')
                    gate_wall=time.perf_counter()-started
                    if weight>0:assert j1<j0 and age<.05 and reason=='earned'
            apply_ns=time.perf_counter_ns()
            if packet_meta is not None:
                sim_age,wall_age,effective_age=packet_ages(packet_meta,t,apply_ns)
                age=effective_age
                if effective_age>=.05:
                    command,weight,reason,j0,j1=gate.reset(baseline,'age_at_apply')
            # Native simulator diagnostics are development interface tests. A wall
            # deadline overrun revokes learned authority, never relabels timing.
            deadline_miss=apply_ns>deadline_ns
            if deadline_miss and mode=='causal_student':
                command,weight,reason,j0,j1=gate.reset(baseline,'deadline')
            last_command=command
            command=float(np.clip(command,-.5,.5));before=actuator
            for _ in range(steps):
                actuator=float(np.clip(actuator+dt*np.clip((command-actuator)/.05,-.35,.35),-.5,.5))
                d.setSteeringAngle(-actuator);d.setCruisingSpeed(speed*3.6)
                if d.step()==-1:raise RuntimeError('unexpected stop')
            post,measured_speed=state();post[0]-=x_origin
            ref_y,ref_psi,_=path_values(post[0],path);error=post[1]-ref_y
            row={'step':i+1,'t_command_s':t,'t_state_s':d.getTime(),'t_test_s':t-t_origin,'command_rad':command,
                 'actuator_rad':actuator,'actuator_rate_rad_s':(actuator-before)/.01,
                 'measured_center_angle_rad':-(left.getValue()+right.getValue())/2,
                 'speed_target_m_s':speed,'speed_truth_m_s':measured_speed,'x_cg_m':post[0],'y_cg_m':post[1],
                 'heading_rad':post[2],'vy_truth_m_s':post[3],'yaw_rate_rad_s':post[4],'reference_y_m':ref_y,
                 'error_m':error,'heading_error_rad':post[2]-ref_psi,'estimated_error_m':estimate[0],
                 'estimated_vy_m_s':estimate[1],'ppo_weight':weight,'command_age_s':age,'ppo_available':available,
                 'inference_wall_s':model_inference_wall,
                 'inference_start_wall_s':packet_meta['entered_ns']/1e9 if packet_meta else 0.,
                 'inference_end_wall_s':packet_meta['inferred_ns']/1e9 if packet_meta else 0.,
                 't_observation_s':packet_meta['observed_sim_s'] if packet_meta else 0.,
                 'gate_observation_equivalent_sim_s':output[1] if output else 0.,
                 't_available_sim_s':t if mode=='causal_student' and received is not None else 0.,
                 't_sensor_sample_s':max(t_origin,t-case.get('sensor_delay_steps',0)*.01),
                 'worker_dropped_requests':0,
                 'wall_release_ns':release_ns,'wall_apply_ns':apply_ns,'wall_deadline_ns':deadline_ns,
                 'wall_response_ms':(apply_ns-(deadline_ns-10_000_000))/1e6,
                 'control_wall_ms':(apply_ns-release_ns)/1e6,'deadline_miss':int(deadline_miss),
                 'wall_action_age_s':wall_age,'sim_action_age_s':sim_age,'effective_action_age_s':effective_age,
                 'packet_observed_wall_ns':inference_observed_ns,'worker_failed':int(bool(worker and worker.failed)),
                 'supervisor_reason':reason,'lqr_command_rad':baseline,'gate_wall_s':gate_wall,
                 'predicted_lqr_cost':j0 if math.isfinite(j0) else 0.,
                 'predicted_candidate_cost':j1 if math.isfinite(j1) else 0.,
                 'prediction_available':int(math.isfinite(j0) and math.isfinite(j1)),
                 'output_sequence':output[0] if output else 0}
            if not all(math.isfinite(value) for key,value in row.items() if key!='supervisor_reason'):raise RuntimeError('nonfinite telemetry')
            if writer is None:writer=csv.DictWriter(stream,fieldnames=row,lineterminator='\n');writer.writeheader()
            writer.writerow(row);records.append(row)
            if mode!='open' and (abs(error)>2.5 or abs(post[2]-ref_psi)>.6):failure='tracking_envelope';break
    steady=[r for r in records if r['t_test_s']>=case.get('duration',12)-2]
    if not steady:steady=records[-100:]
    metrics={'case':case,'steps':len(records),'survived':failure is None,'failure':failure,
             'scheduled_steps':round(case['duration']/.01),
             'penalized_rmse_m':float(np.sqrt((sum(r['error_m']**2 for r in records)+(round(case['duration']/.01)-len(records))*6.25)/round(case['duration']/.01))),
             'mean_weight':float(np.mean([r['ppo_weight'] for r in records])),
             'rmse_m':float(np.sqrt(np.mean([r['error_m']**2 for r in records]))),
             'max_abs_error_m':max(abs(r['error_m']) for r in records),'final':records[-1],
             'steady_curvature_per_m':float(np.mean([r['yaw_rate_rad_s']/r['speed_truth_m_s'] for r in steady])),
             'steady_speed_m_s':float(np.mean([r['speed_truth_m_s'] for r in steady])),
             'max_actuator_rate_rad_s':max(abs(r['actuator_rate_rad_s']) for r in records),
             'fallback_fraction':sum(r['ppo_weight']==0 for r in records)/len(records) if mode=='causal_student' else None,
             'native_deadline_misses':sum(r['deadline_miss'] for r in records),
             'stale_authority_violations':sum(r['effective_action_age_s']>=.05 and r['ppo_weight']!=0 for r in records),
             'late_authority_violations':sum(r['deadline_miss'] and r['ppo_weight']!=0 for r in records),
             'worker_failed':worker.failed if worker else None}
    if packet_log:
        with (out/'packets.json').open('w') as f:json.dump(packet_log,f)
    assert metrics['max_actuator_rate_rad_s']<=.35000001
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')

if __name__=='__main__':
    d=Driver()
    try:main(d)
    except Exception:
        Path(os.environ['LANS_CASE_CONFIG']).with_suffix('.failure.txt').write_text(traceback.format_exc());traceback.print_exc();d.simulationQuit(1)
    else:d.simulationQuit(0)
