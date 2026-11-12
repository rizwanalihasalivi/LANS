"""Isolated, source-pinned, policy-free native drivetrain calibration."""
from pathlib import Path
import argparse,json,os,shutil,time
import numpy as np
from .native import copy_protos,run_process
from .runtime import sha

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent


def run(output,lookaheads=(.05,.2,1.),speeds=(8.,12.,16.,17.25),duration=1.5,method='cruise_lookahead'):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    project=output/'project';(project/'worlds').mkdir(parents=True);protos=copy_protos(project)
    controller=project/'controllers/v13_calibration';controller.mkdir(parents=True)
    entry=controller/'v13_calibration.py'
    entry.write_text("import os,runpy,sys\nsys.path.insert(0,os.environ['LANS_ROOT'])\nrunpy.run_module('tools.ppo_complete_v13.native_assets.calibration_controller',run_name='__main__')\n")
    source=ROOT/'integrations/webots/worlds/publication_v9.wbt'
    world=source.read_text().replace('../.runtime/protos','../protos').replace('controller "publication_v9"','controller "v13_calibration"')
    world=world.replace('  engineType "electric"','  engineType "electric"\n  engineMaxPower 100000')
    if method=='torque_pi':
        world=world.replace('  engineMaxPower 100000','  engineMaxPower 100000\n  brakeCoefficient 1000')
        world=world.replace('  wheelsDampingConstant 5','  wheelsDampingConstant 0.2')
    worldpath=project/'worlds/calibration.wbt';worldpath.write_text(world)
    cases=[dict(initial_speed_m_s=v,requested_accel_m_s2=a,lookahead_s=t)
        for t in lookaheads for v in speeds for a in (2.5,-6.)]
    files=[Path(__file__),HERE/'actuation.py',HERE/'native_assets/calibration_controller.py',source,ROOT/'tools/cloud/run-webots.sh']
    protocol=dict(role='policy_free_actuator_calibration_before_final_native',webots='R2025a',cases=cases,duration_s=duration,actuation_method=method,
        native_engine_max_power_w=100000,native_max_speed_m_s=50.,native_nominal_mass_kg=1650.,
        engine_model_used=method=='torque_pi',brake_coefficient_nm=1000 if method=='torque_pi' else 700,
        wheel_joint_damping=.2 if method=='torque_pi' else 5.,
        damping_rationale='D=.2 bounds four-wheel viscous coast loss below .1m/s2 at20m/s:4*D*v/(1650*.32^2)=.094697. Frozen policy-free matching of the acceleration-command plant; same for every controller.',
        power_rationale='m*a*v=1650*2.5*20=82500W before drivetrain losses;100kW chosen before any final policy outcome, shared by every controller.',
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},protos=protos,world_sha256=sha(worldpath),
        physical_actuation=('Webots Driver electric-engine TORQUE and four-wheel mechanical brakes' if method=='torque_pi' else 'Webots Driver velocity-motor SPEED mode; engine power is not used in this mode')+'; no pose/velocity/force overwrites or Python integration',
        selection='One global lookahead by mean settled acceleration RMSE across all conditions; no policy or case53 selection.')
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2,allow_nan=False)+'\n')
    for p in files:
        target=output/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_ACTUATION_OUTPUT=str(output),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    start=time.monotonic()
    with (output/'console.log').open('w') as log:
        run_process(['bash',str(ROOT/'tools/cloud/run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(worldpath)],env,log,240.)
    summary=json.loads((output/'summary.json').read_text());assert summary['completed'] and summary['conditions']==len(cases)
    records=summary['records'];rank={str(t):float(np.mean([r['settled_accel_rmse_m_s2'] for r in records if r['case']['lookahead_s']==t])) for t in lookaheads}
    selected=min(lookaheads,key=lambda t:rank[str(t)])
    result=dict(completed=True,policy_tested=False,final_controller_tested=False,conditions=len(cases),
        aggregate_settled_accel_rmse_m_s2=rank,selected_common_lookahead_s=selected,
        wall_elapsed_s=time.monotonic()-start,all_initial_speeds_settled=all(abs(r['initial_measured_speed_m_s']-r['case']['initial_speed_m_s'])<=.1 for r in records),
        raw_sha256={p.name:sha(p) for p in output.glob('condition-*.jsonl')},protocol_sha256=sha(output/'protocol.json'),
        summary_sha256=sha(output/'summary.json'),scope='Calibration evidence only; actual policy/safety/heading/deadline transfer remains untested.')
    (output/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2),flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--lookaheads',type=float,nargs='+',default=[.05,.2,1.]);p.add_argument('--speeds',type=float,nargs='+',default=[8.,12.,16.,17.25]);p.add_argument('--duration',type=float,default=1.5)
    p.add_argument('--method',choices=['cruise_lookahead','torque_pi'],default='cruise_lookahead')
    a=p.parse_args();run(a.output,tuple(a.lookaheads),tuple(a.speeds),a.duration,a.method)


if __name__=='__main__':main()
