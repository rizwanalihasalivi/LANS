"""Run a fresh Webots process with an immutable per-case configuration and generated world."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from native_process import run_native
ROOT=Path(__file__).resolve().parents[1]

def create_case_project(destination):
    # Different output runs may execute the same case name concurrently.
    project=ROOT/'.runtime/cases'/hashlib.sha256(str(destination.resolve()).encode()).hexdigest()[:20]
    (project/'worlds').mkdir(parents=True,exist_ok=False)
    (project/'controllers').symlink_to(ROOT/'controllers',target_is_directory=True)
    return project

def run(case,name,output):
    destination=Path(output).resolve()/name;destination.mkdir(parents=True,exist_ok=False)
    project=create_case_project(destination)
    case=dict(case)
    if case.get('policy'):
        policy=Path(case['policy']);metadata=json.loads((policy.parent/'complete.json').read_text())
        assert metadata['steps']==1000000 and metadata['training_profile']=='positive_survival_v2'
        case['policy_sha256']=hashlib.sha256(policy.read_bytes()).hexdigest()
        assert case['policy_sha256']==metadata['policy_sha256']
    case.setdefault('lateral_slip',4*case['speed']/80000)
    world=(ROOT/'worlds/research_validation.wbt').read_text().replace('../.runtime/protos',str(ROOT/'.runtime/protos'))
    calibration=json.loads((ROOT/'research/calibration.json').read_text())
    case['front_slip']=case['lateral_slip']*calibration['front_slip_multiplier']
    case['rear_slip']=case['lateral_slip']*calibration['rear_slip_multiplier']
    world=world.replace('forceDependentSlip [ 0 0 ] # FRONT_SLIP',f"forceDependentSlip [ {case['front_slip']} 0 ]")
    world=world.replace('forceDependentSlip [ 0 0 ] # REAR_SLIP',f"forceDependentSlip [ {case['rear_slip']} 0 ]")
    world=world.replace('basicTimeStep 1',f"basicTimeStep {case.get('physics_ms',1)}")
    world_path=project/'worlds/test.wbt';world_path.write_text(world)
    (destination/'generated-world.wbt').write_text(world)
    case=dict(case,output=str(destination))
    config=destination/'case.json';config.write_text(json.dumps(case,indent=2)+'\n')
    source_files=['research/core.py','research/protocol.json','research/run-physical.py','research/native_process.py','controllers/research_validation/research_validation.py','worlds/research_validation.wbt','research/comparison.py','research/comparison-protocol.json','research/worker.py','run-research-webots.sh','research/calibration.json','research/tracking.py','research/tracking-protocol.json']
    for filename in source_files:
        target=destination/'source'/filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/filename).read_bytes())
    (destination/'inputs.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files},indent=2)+'\n')
    environment=os.environ.copy();environment.update(LANS_INTEGRATION_ROOT=str(ROOT),LANS_CASE_CONFIG=str(config),
        PATH=str(Path(environment.get('LANS_PYTHON','/workspace/lans-setup/venv/bin/python')).parent)+':'+environment['PATH'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        NUMBA_CACHE_DIR=str(ROOT/'.runtime/numba'),MPLCONFIGDIR=str(ROOT/'.runtime/mpl'))
    with (destination/'console.log').open('w') as log:
        run_native(['bash',str(ROOT/'run-research-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(world_path)],env=environment,stdout=log,timeout=240)
    metrics=json.loads((destination/'metrics.json').read_text())
    print(name,metrics['survived'],metrics['rmse_m'],flush=True)
    return metrics

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--suite',choices=['development','tracking','transfer'],default='development');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--wait-for-training',action='store_true');args=parser.parse_args()
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    results={}
    if args.suite in ('development','tracking'):
        for speed in (15,20,25):
            for angle in ((0.,.003,-.003) if args.suite=='development' else ()):
                name=f'open-v{speed}-d{angle}'
                results[name]=run(dict(mode='open',speed=speed,angle=angle,noise=0,duration=8),name,args.output)
            for noise,delay in ((0,0),(1,0),(1,1)):
                name=f'lqr-v{speed}-noise{noise}-delay{delay}'
                results[name]=run(dict(mode='lqr',speed=speed,path='dlc220',noise=noise,sensor_delay_steps=delay,duration=220/speed+2),name,args.output)
        for physics in ((2,5,10) if args.suite=='development' else ()):
            name=f'convergence-{physics}ms'
            results[name]=run(dict(mode='open',speed=25,angle=.003,noise=0,duration=8,physics_ms=physics),name,args.output)
    else:
        for seed in range(5):
            if args.wait_for_training:
                complete=ROOT/f'results/research-training/full-{seed}/complete.json';deadline=time.monotonic()+3600
                if not complete.exists():print(f'Waiting for final full-{seed} transfer checkpoint',flush=True)
                while not complete.exists():
                    if time.monotonic()>deadline:raise TimeoutError(str(complete))
                    time.sleep(5)
            for speed in (15,20,25):
                for mode,delay in (('ppo',0),('fusion',0),('fusion',100)):
                    name=f'{mode}-seed{seed}-v{speed}-delay{delay}'
                    results[name]=run(dict(mode=mode,speed=speed,path='dlc220',noise=1,seed=20000+seed,delay_ms=delay,
                         policy=str(ROOT/f'results/research-training/full-{seed}/policy.zip'),duration=220/speed+2),name,args.output)
    (args.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
