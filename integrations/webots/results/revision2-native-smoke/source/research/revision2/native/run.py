"""No-retuning native transfer runner: new evidence, real worker, fixed grid."""
import argparse,concurrent.futures,hashlib,itertools,json,os,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROTOCOL=json.loads((HERE/'protocol.json').read_text())
FREEZE=ROOT/'results/revision2-development/freeze.json'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
SOURCES=['research/core.py','research/protocol.json','research/comparison.py','research/comparison-protocol.json',
         'research/tracking.py','research/tracking-protocol.json','research/worker.py','research/calibration.json',
         'research/revision2/gating.py','research/revision2/native/run.py','research/revision2/native/protocol.json',
         'controllers/gated_validation/gated_validation.py','worlds/research_validation.wbt','run-gated-webots.sh',
         'results/revision2-development/freeze.json']

def validate_frozen():
    frozen=json.loads(FREEZE.read_text())
    for name,digest in frozen['source_sha256'].items():assert sha(ROOT/'research'/name)==digest,f'Frozen source changed: {name}'
    for name,digest in frozen['policy_sha256'].items():assert sha(ROOT/'results/research-training'/name/'policy.zip')==digest
    assert frozen['selected_config']=={'horizon_steps':20,'relative_margin':.01}
    return frozen

def run(case,name,output,source_hashes):
    destination=output/name;destination.mkdir()
    project=ROOT/'.runtime/native-cases'/hashlib.sha256(str(destination).encode()).hexdigest()[:20]
    (project/'worlds').mkdir(parents=True,exist_ok=False)
    (project/'controllers').symlink_to(ROOT/'controllers',target_is_directory=True)
    calibration=json.loads((ROOT/'research/calibration.json').read_text())
    case=dict(case,output=str(destination))
    case['front_slip']=4*case['speed']/80000*calibration['front_slip_multiplier']/case['contact_scale']
    case['rear_slip']=4*case['speed']/80000*calibration['rear_slip_multiplier']/case['contact_scale']
    world=(ROOT/'worlds/research_validation.wbt').read_text().replace('../.runtime/protos',str(ROOT/'.runtime/protos'))
    world=world.replace('controller "research_validation"','controller "gated_validation"')
    world=world.replace('coulombFriction [ 0.9 ]',f"coulombFriction [ {case['mu']} ]")
    for key in ('front','rear'):
        world=world.replace(f'forceDependentSlip [ 0 0 ] # {key.upper()}_SLIP',f"forceDependentSlip [ {case[key+'_slip']} 0 ]")
    world_path=project/'worlds/test.wbt';world_path.write_text(world);(destination/'generated-world.wbt').write_text(world)
    config=destination/'case.json';config.write_text(json.dumps(case,indent=2)+'\n')
    env=os.environ.copy();python=env.get('LANS_PYTHON',str(ROOT/'.runtime/research-venv/bin/python'))
    assert Path(python).is_file()
    env.update(LANS_INTEGRATION_ROOT=str(ROOT),LANS_CASE_CONFIG=str(config),PATH=str(Path(python).parent)+':'+env['PATH'],
               OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',NUMBA_CACHE_DIR=str(ROOT/'.runtime/numba'),MPLCONFIGDIR=str(ROOT/'.runtime/mpl'))
    started=time.time()
    with (destination/'console.log').open('w') as log:
        subprocess.run(['bash',str(ROOT/'run-gated-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(world_path)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=360)
    metrics=json.loads((destination/'metrics.json').read_text())
    assert metrics['case']==case
    provenance=dict(started_unix_s=started,elapsed_wall_s=time.time()-started,python=python,source_sha256=source_hashes,
                    generated_world_sha256=sha(destination/'generated-world.wbt'),config_sha256=sha(config),telemetry_sha256=sha(destination/'telemetry.csv'),metrics_sha256=sha(destination/'metrics.json'))
    (destination/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(name,metrics['survived'],metrics['penalized_rmse_m'],flush=True)
    return name,metrics

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['smoke','reserved']);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    frozen=validate_frozen();source_hashes={name:sha(ROOT/name) for name in SOURCES}
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    for name in SOURCES:
        target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    (output/'start.json').write_text(json.dumps(dict(phase=args.phase,protocol=PROTOCOL,source_sha256=source_hashes,freeze_sha256=sha(FREEZE),policy_sha256=frozen['policy_sha256']),indent=2)+'\n')
    cases=[]
    grid=itertools.product(PROTOCOL['seeds'],PROTOCOL['speeds'],PROTOCOL['scenarios'],PROTOCOL['methods']) if args.phase=='reserved' else [(0,20,'nominal',m) for m in PROTOCOL['methods']]
    for seed,speed,scenario,method in grid:
        spec=PROTOCOL['scenarios'][scenario]
        noise_seed=PROTOCOL['noise_seed_base']+seed*10000+speed*100+list(PROTOCOL['scenarios']).index(scenario) if args.phase=='reserved' else 880001
        case=dict(spec,mode=method,speed=speed,path='dlc220',seed=noise_seed,policy_seed=seed,scenario=scenario,duration=220/speed+2,gate_config=frozen['selected_config'])
        if method!='lqr':
            role='residual' if method=='gated_residual' else 'full';policy=ROOT/f'results/research-training/{role}-{seed}/policy.zip'
            case.update(policy=str(policy),policy_sha256=sha(policy))
        name=f'{scenario}-seed{seed}-v{speed}-{method}';cases.append((case,name))
    results={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=PROTOCOL['parallel_webots_processes']) as pool:
        futures=[pool.submit(run,case,name,output,source_hashes) for case,name in cases]
        for future in concurrent.futures.as_completed(futures):
            name,metrics=future.result();results[name]=metrics
    assert len(results)==(270 if args.phase=='reserved' else 3)
    assert source_hashes=={name:sha(ROOT/name) for name in SOURCES};validate_frozen()
    (output/'summary.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    (output/'complete.json').write_text(json.dumps(dict(cases=len(results),summary_sha256=sha(output/'summary.json'),source_sha256=source_hashes),indent=2)+'\n')
if __name__=='__main__':main()
