"""Run a fresh Webots process with an immutable per-case configuration and generated world."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(case,name,output):
    destination=output/name;destination.mkdir(parents=True,exist_ok=False)
    project=ROOT/'.runtime/cases'/name; (project/'worlds').mkdir(parents=True,exist_ok=True)
    if not (project/'controllers').exists():(project/'controllers').symlink_to(ROOT/'controllers',target_is_directory=True)
    case=dict(case)
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
    source_files=['research/core.py','research/protocol.json','research/run-physical.py','controllers/research_validation/research_validation.py','worlds/research_validation.wbt','research/comparison.py','research/comparison-protocol.json','research/worker.py','run-research-webots.sh','research/calibration.json']
    for filename in source_files:
        target=destination/'source'/filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/filename).read_bytes())
    (destination/'inputs.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files},indent=2)+'\n')
    environment=os.environ.copy();environment.update(LANS_INTEGRATION_ROOT=str(ROOT),LANS_CASE_CONFIG=str(config),
        PATH=str(Path(environment.get('LANS_PYTHON','/workspace/lans-setup/venv/bin/python')).parent)+':'+environment['PATH'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        NUMBA_CACHE_DIR=str(ROOT/'.runtime/numba'),MPLCONFIGDIR=str(ROOT/'.runtime/mpl'))
    with (destination/'console.log').open('w') as log:
        subprocess.run(['bash',str(ROOT/'run-research-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(world_path)],env=environment,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    metrics=json.loads((destination/'metrics.json').read_text())
    print(name,metrics['survived'],metrics['rmse_m'],flush=True)
    return metrics

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--suite',choices=['development','transfer'],default='development');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    results={}
    if args.suite=='development':
        for speed in (15,20,25):
            for angle in (0.,.003,-.003):
                name=f'open-v{speed}-d{angle}'
                results[name]=run(dict(mode='open',speed=speed,angle=angle,noise=0,duration=8),name,args.output)
            for noise,delay in ((0,0),(1,0),(1,1)):
                name=f'lqr-v{speed}-noise{noise}-delay{delay}'
                results[name]=run(dict(mode='lqr',speed=speed,path='dlc220',noise=noise,sensor_delay_steps=delay,duration=220/speed+2),name,args.output)
        for physics in (2,5,10):
            name=f'convergence-{physics}ms'
            results[name]=run(dict(mode='open',speed=25,angle=.003,noise=0,duration=8,physics_ms=physics),name,args.output)
    else:
        for seed in range(5):
            for speed in (15,20,25):
                for mode,delay in (('ppo',0),('fusion',0),('fusion',100)):
                    name=f'{mode}-seed{seed}-v{speed}-delay{delay}'
                    results[name]=run(dict(mode=mode,speed=speed,path='dlc220',noise=1,seed=10000+seed,delay_ms=delay,
                         policy=str(ROOT/f'results/research-training/full-{seed}/policy.zip'),duration=220/speed+2),name,args.output)
    (args.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
