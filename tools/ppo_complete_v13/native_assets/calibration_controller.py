"""Policy-free longitudinal calibration using actual Webots wheel/body physics."""
import json,math,os,traceback
from pathlib import Path
import numpy as np
from tools.ppo_complete_v13.actuation import LongitudinalActuator,TorqueActuator,measured_forward_speed


def main(driver):
    out=Path(os.environ['LANS_ACTUATION_OUTPUT']);p=json.loads((out/'protocol.json').read_text())
    node=driver.getSelf();dt=driver.getBasicTimeStep()/1000
    assert abs(dt-.001)<1e-12
    driver.setSteeringAngle(0.);summaries=[]
    for index,case in enumerate(p['cases']):
        target=case['initial_speed_m_s'];driver.setBrakeIntensity(0.);driver.setCruisingSpeed(target*3.6)
        # Native warmup/settling only. No Python ego integration or repeated
        # state overwrite occurs during a measured segment.
        stable=0;warm=0
        while warm<10000:
            if driver.step()==-1:raise RuntimeError('native stopped during actuator warmup')
            v=measured_forward_speed(node);warm+=1
            stable=stable+1 if abs(v-target)<.08 else 0
            if warm>=1000 and stable>=200:break
        initial=measured_forward_speed(node);t0=driver.getTime()
        actuator=TorqueActuator() if p.get('actuation_method')=='torque_pi' else LongitudinalActuator(lookahead_s=case['lookahead_s'])
        rows=[];path=out/f'condition-{index:03d}.jsonl'
        with path.open('x') as stream:
            for tick in range(round(p['duration_s']/dt)):
                before=measured_forward_speed(node);metadata=actuator.update(driver,before,case['requested_accel_m_s2'],dt)
                position_before=list(node.getPosition());time_before=driver.getTime()
                if driver.step()==-1:raise RuntimeError('native stopped during measured actuator segment')
                after=measured_forward_speed(node);achieved=(after-before)/dt
                row=dict(index=index,tick=tick,simulation_before_s=time_before,simulation_after_s=driver.getTime(),
                    physical_position_before=position_before,physical_position_after=list(node.getPosition()),
                    speed_before_m_s=before,speed_after_m_s=after,achieved_accel_m_s2=achieved,**metadata)
                stream.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
        values=np.array([r['achieved_accel_m_s2'] for r in rows]);times=np.arange(len(rows))*dt
        settled=values[times>=.2];errors=settled-case['requested_accel_m_s2']
        reached=np.flatnonzero(np.abs(values-case['requested_accel_m_s2'])<=.25)
        result=dict(case=case,initial_measured_speed_m_s=initial,warmup_physics_steps=warm,
            warmup_simulation_s=warm*dt,rows=len(rows),measured_duration_s=driver.getTime()-t0,
            mean_accel_m_s2=float(values.mean()),settled_mean_accel_m_s2=float(settled.mean()),
            settled_accel_rmse_m_s2=float(np.sqrt(np.mean(errors*errors))),
            settled_min_accel_m_s2=float(settled.min()),settled_max_accel_m_s2=float(settled.max()),
            first_reach_within_025_s=None if len(reached)==0 else float(times[reached[0]]),
            final_speed_m_s=rows[-1]['speed_after_m_s'],native_body_integrated=True,
            python_ego_integrated=False,pose_overwritten=False,velocity_overwritten=False)
        summaries.append(result);(out/'partial-summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    result=dict(role='policy_free_native_actuation_calibration',completed=True,conditions=len(summaries),records=summaries,
        policy_tested=False,final_controller_tested=False,physics_step_s=dt)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    from vehicle import Driver
    d=Driver();out=Path(os.environ['LANS_ACTUATION_OUTPUT'])
    try:main(d)
    except BaseException:
        (out/'failure.txt').write_text(traceback.format_exc());traceback.print_exc();d.simulationQuit(1)
    else:d.simulationQuit(0)
