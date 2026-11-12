"""Isolated native Webots launchers; readiness is separate from final transfer."""
from pathlib import Path
import argparse,json,math,os,shutil,subprocess,time
from .runtime import sha

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent


def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def copy_protos(project):
    hashes={};manifest=ROOT/'integrations/webots/runtime-sha256.txt'
    roots=[ROOT/'integrations/webots/.runtime',Path('/workspace/LANS/integrations/webots/.runtime')]
    for line in manifest.read_text().splitlines():
        digest,name=line.split()
        if not name.startswith('protos/'):continue
        source=next((root/name for root in roots if (root/name).is_file()),None)
        if source is None:raise FileNotFoundError('Restore the pinned Webots PROTO cache: '+name)
        assert sha(source)==digest,('Native PROTO source changed',name)
        target=project/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        hashes[name]=digest
    assert len(hashes)==5
    return hashes


def run_process(command,env,log,timeout):
    import signal
    process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=process.wait(timeout=timeout)
    except BaseException:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=5.)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait()
        raise
    if code:raise subprocess.CalledProcessError(code,command)


def readiness(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    project=output/'project';(project/'worlds').mkdir(parents=True)
    protos=copy_protos(project)
    controller=project/'controllers/v13_readiness';controller.mkdir(parents=True)
    source=HERE/'native_assets/readiness.py';target=controller/'v13_readiness.py';shutil.copyfile(source,target)
    worldsource=ROOT/'integrations/webots/worlds/publication_v9.wbt'
    world=worldsource.read_text().replace('../.runtime/protos','../protos').replace('controller "publication_v9"','controller "v13_readiness"')
    worldpath=project/'worlds/readiness.wbt';worldpath.write_text(world)
    protocol=dict(role='environment_readiness_only',webots='R2025a',duration_s=2.,physics_step_s=.001,
        policy_tested=False,final_controller_tested=False,native_ego_physics=True,protos=protos,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),source,worldsource,ROOT/'tools/cloud/run-webots.sh')},
        generated_world_sha256=sha(worldpath),limitation='Single physical vehicle; no tracking, traffic, learned-policy or final safety claim.')
    dump(output/'protocol.json',protocol);env=os.environ.copy();env['LANS_NATIVE_OUTPUT']=str(output)
    start=time.monotonic()
    with (output/'console.log').open('w') as log:
        run_process(['bash',str(ROOT/'tools/cloud/run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(worldpath)],env,log,120.)
    result=json.loads((output/'summary.json').read_text());assert result['passed'] and result['ticks']==2000
    assert not result['policy_tested'] and not result['final_controller_tested']
    dump(output/'provenance.json',dict(protocol_sha256=sha(output/'protocol.json'),raw_sha256=sha(output/'ticks.jsonl'),
        world_sha256=sha(worldpath),elapsed_wall_s=time.monotonic()-start,summary_sha256=sha(output/'summary.json')))
    print(json.dumps(result),flush=True);return result


def prepare_episode(output,fixture,mode,policy=None,role='opened_development_bridge'):
    """Build a fresh physical world without running/opening any other fixtures."""
    import numpy as np
    from tools.unified_control_v9.learning import setup
    from tools.ppo_benefit_v10.core import PARAMS
    from .learning import controller_class
    from .train import CONTROLLER_KWARGS
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    assert mode in ('lqr','adaptive','ppo','bc','continued_bc')
    if mode in ('ppo','bc','continued_bc'):
        from .runtime import load_policy
        from .learning import CONTRACT
        policy=Path(policy).resolve();load_policy(policy,CONTRACT,55,bc=mode=='bc')
    c,_,initial,npcs,_=setup(fixture,'lqr' if mode=='lqr' else 'deterministic',controller_class(),
        dict(PARAMS,**CONTROLLER_KWARGS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
    route_kind=c.route.kind;_,heading,_=c.route.geometry(0.)
    project=output/'project';(project/'worlds').mkdir(parents=True);protos=copy_protos(project)
    source=ROOT/'integrations/webots/worlds/publication_v9.wbt'
    prefix,car=source.read_text().replace('../.runtime/protos','../protos').split('DEF VEHICLE Car {',1)
    calibration=ROOT/'integrations/webots/research/calibration.json';tire=json.loads(calibration.read_text())
    slip=4*fixture['speed']/(80000*fixture['stiffness'])
    front=slip*tire['front_slip_multiplier'];rear=slip*tire['rear_slip_multiplier']
    prefix=prefix.replace('forceDependentSlip [ 0 0 ] # FRONT_SLIP',f'forceDependentSlip [ {front:.16g} {front:.16g} ] # FRONT_SLIP')
    prefix=prefix.replace('forceDependentSlip [ 0 0 ] # REAR_SLIP',f'forceDependentSlip [ {rear:.16g} {rear:.16g} ] # REAR_SLIP')
    car=car.replace('  engineType "electric"','  engineType "electric"\n  engineMaxPower 100000\n  brakeCoefficient 1000')
    car=car.replace('  wheelsDampingConstant 5','  wheelsDampingConstant 0.2')
    ego=car.replace('controller "publication_v9"','controller "v13_native"')
    world=prefix+'DEF VEHICLE Car {'+ego;npc_defs={}
    for i,(name,state) in enumerate(npcs.items()):
        defname='NPC_'+str(i);npc_defs[name]=defname
        angle=float(state[2]-heading-fixture['heading'])
        body=car.replace('controller "publication_v9"','controller "v13_npc"')
        body=body.replace('translation 0 0 0.36',f'translation {-100-20*i} {100+30*i} 0.36\n  rotation 0 0 1 {angle:.16g}',1)
        body=body.replace('name "lans-validation-surrogate"',f'name "{name}"',1)
        world+='\nDEF '+defname+' Car {'+body
    for name,module in [('v13_native','driver'),('v13_npc','npc')]:
        directory=project/'controllers'/name;directory.mkdir(parents=True)
        (directory/(name+'.py')).write_text("import os,runpy,sys\nsys.path.insert(0,os.environ['LANS_ROOT'])\nif __name__=='__main__':\n    runpy.run_module('tools.ppo_complete_v13.native_assets."+module+"',run_name='__main__')\n")
    worldpath=project/'worlds/episode.wbt';worldpath.write_text(world)
    case=dict(fixture,output=str(output),mode=mode,role=role,route_kind=route_kind,
        policy=None if policy is None else str(policy),controller_kwargs=CONTROLLER_KWARGS,
        initial_ego=initial.tolist(),initial_npcs={n:z.tolist() for n,z in npcs.items()},npc_defs=npc_defs)
    dump(output/'case.json',case)
    files=[Path(__file__),HERE/'native_adapter.py',HERE/'actuation.py',HERE/'native_assets/driver.py',HERE/'native_assets/npc.py',
        HERE/'runtime.py',HERE/'learning.py',HERE/'plans.py',HERE/'safety.py',source,calibration,ROOT/'tools/cloud/run-webots.sh']
    files.extend((ROOT/'integrations/unified_lans').glob('*.py'))
    for version in range(4,9):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    for p in files:
        target=output/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    model_hash=None if policy is None else sha(policy/('bc-policy.zip' if mode=='bc' else 'policy.zip'))
    dump(output/'protocol.json',dict(case_sha256=sha(output/'case.json'),source_hashes=hashes,protos=protos,
        world_sha256=sha(worldpath),policy_sha256=model_hash,role=role,physics_step_s=.001,controller_step_s=.05,
        native_ego_physics=True,native_traffic_physics=True,traffic_state_integrated_in_python=False,
        collision_geometry='Original2.3m circles evaluated on actual1ms native poses; mesh contact is separate',
        physical_initialization='10s physical warmup; fixed ego map transform and single traffic translation before measurement; no subsequent state writes',
        torque_actuator_calibration_sha256=sha(ROOT/'results/ppo-complete-v13/native-actuator-calibration-v3/verification.json'),
        physical_vehicle=dict(total_mass_kg=1650.,wheel_damping=.2,engine_power_w=100000,brake_coefficient=1000,
            front_fds=front,rear_fds=rear),fairness='Same vehicle/initialization/tire law for every matched method; actual stiffness is hidden from controller'))
    return output,worldpath


def episode(output,fixture,mode,policy=None,role='opened_development_bridge'):
    output,world=prepare_episode(output,fixture,mode,policy,role)
    env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_NATIVE_CASE=str(output/'case.json'),
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='2')
    start=time.monotonic()
    with (output/'console.log').open('w') as log:
        run_process(['bash',str(ROOT/'tools/cloud/run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(world)],env,log,180.)
    result=json.loads((output/'summary.json').read_text())
    dump(output/'provenance.json',dict(protocol_sha256=sha(output/'protocol.json'),raw_sha256=sha(output/'ticks.jsonl'),
        summary_sha256=sha(output/'summary.json'),elapsed_wall_s=time.monotonic()-start,policy_sha256=json.loads((output/'protocol.json').read_text())['policy_sha256']))
    print(json.dumps(result),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--readiness',action='store_true');parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',type=Path);parser.add_argument('--id',type=int);parser.add_argument('--mode',choices=['lqr','adaptive','ppo','bc','continued_bc'])
    parser.add_argument('--policy',type=Path);parser.add_argument('--role',default='opened_development_bridge')
    args=parser.parse_args()
    if args.readiness:readiness(args.output);return
    if args.cases is None or args.id is None or args.mode is None:parser.error('Native episode requires cases,id,mode')
    fixture=next(c for c in json.loads(args.cases.read_text())['cases'] if c['id']==args.id)
    episode(args.output,fixture,args.mode,args.policy,args.role)


if __name__=='__main__':main()
