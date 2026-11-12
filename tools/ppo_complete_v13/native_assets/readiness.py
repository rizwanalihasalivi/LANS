"""Environment readiness only: a real Webots vehicle moves under wheel physics."""
import json,math,os,traceback
from pathlib import Path


def main(driver):
    out=Path(os.environ['LANS_NATIVE_OUTPUT']);dt=driver.getBasicTimeStep()/1000
    assert abs(dt-.001)<1e-12
    node=driver.getSelf();initial=list(node.getPosition());t0=driver.getTime();rows=[]
    driver.setSteeringAngle(0.);driver.setCruisingSpeed(36.)
    with (out/'ticks.jsonl').open('x') as stream:
        for tick in range(2000):
            before=driver.getTime()
            if driver.step()==-1:raise RuntimeError('simulator stopped during readiness')
            row=dict(tick=tick,simulation_before_s=before,simulation_after_s=driver.getTime(),
                position_world_m=list(node.getPosition()),velocity_world=list(node.getVelocity()))
            assert all(math.isfinite(x) for x in row['position_world_m']+row['velocity_world'])
            stream.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
    moved=math.dist(initial,rows[-1]['position_world_m'])
    assert moved>.05,'No physical vehicle motion measured'
    assert abs(driver.getTime()-t0-2.)<1e-7
    result=dict(passed=True,role='native_environment_readiness_only',physics_step_s=dt,ticks=len(rows),
        duration_s=driver.getTime()-t0,physical_displacement_m=moved,native_ego_physics=True,
        python_ego_integrated=False,ego_pose_overwritten=False,collision_assessed=False,
        final_controller_tested=False,policy_tested=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    from vehicle import Driver
    driver=Driver();out=Path(os.environ['LANS_NATIVE_OUTPUT'])
    try:main(driver)
    except BaseException:
        (out/'failure.txt').write_text(traceback.format_exc());traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)
