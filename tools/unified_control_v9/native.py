"""Fixed native transfer cohort; no policy or simulator tuning on its outcomes."""
from pathlib import Path
import argparse,json,os,shutil,sys,time
from integrations.unified_lans.inference import sha
from .train import selected_kwargs

ROOT=Path(__file__).resolve().parents[2];INTEGRATION=ROOT/'integrations/webots'
DATA=ROOT/'results/publication-v9'
sys.path.insert(0,str(INTEGRATION/'research'))
from native_process import run_native


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def verify_protos():
    paths=[]
    for line in (INTEGRATION/'runtime-sha256.txt').read_text().splitlines():
        digest,name=line.split()
        if name.startswith('protos/'):
            path=INTEGRATION/'.runtime'/name
            assert sha(path)==digest,('Webots PROTO mismatch',name)
            paths.append(path)
    assert len(paths)==5
    return paths


def python_safety():
    folder=DATA/'confirmation'
    status=json.loads((folder/'STATUS.json').read_text())
    assert status['final_once_complete'],'Complete the frozen Python evaluation first'
    selected=[]
    for stage in ['regression-development','regression-stress','development','stress','final']:
        rows=json.loads((folder/f'{stage}_summary.json').read_text())
        selected.extend(r for r in rows if r['mode']=='hybrid')
    assert selected and all(not r['failed'] for r in selected),'Current hybrid Python safety failed; native transfer is gated'
    return dict(episodes=len(selected),failed=sum(r['failed'] for r in selected),status_sha256=sha(folder/'STATUS.json'),
        summary_sha256={p.name:sha(p) for p in folder.glob('*_summary.json')})


def definitions(smoke):
    pairs=[('straight',10.)] if smoke else [(route,speed) for route in ('straight','sine') for speed in (8.,16.)]
    result=[]
    for route,speed in pairs:
        for mode,seed in [('lqr',0),('hybrid',42)] if smoke else [('lqr',0),('hybrid',42),('hybrid',43),('hybrid',44)]:
            result.append(dict(name=f'{route}-{speed:g}-{mode}-{seed}',route=route,speed=speed,mode=mode,seed=seed,
                phase=.5 if smoke else 9.,amplitude=1.15,lateral=.3,heading=.005,duration=.5 if smoke else 6.,
                controller_kwargs=selected_kwargs(),policy=str(DATA/'policies'/f'seed-{seed}') if seed else None))
    return result


def prepare(output,smoke):
    protos=verify_protos();safety=None if smoke else python_safety()
    output.mkdir(parents=True,exist_ok=False)
    own=Path(__file__).parent
    files=[*(own/name for name in ['native.py','native_adapter.py','NATIVE_PROTOCOL.md','control.py','runtime.py','train.py']),
        INTEGRATION/'controllers/publication_v9/publication_v9.py',INTEGRATION/'worlds/publication_v9.wbt',
        INTEGRATION/'research/calibration.json',INTEGRATION/'research/native_process.py',ROOT/'tools/cloud/run-webots.sh',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py',*protos]
    for version in range(4,9):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    protocol=dict(kind='technical_smoke' if smoke else 'fixed_native_single_vehicle_transfer',smoke=smoke,
        webots='R2025a',cases=definitions(smoke),python_safety=safety,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        policies={str(s):sha(DATA/'policies'/f'seed-{s}'/'policy.zip') for s in (42,43,44)},
        limitations=['No traffic, collision or communication validation in this single-vehicle world.',
            'Native tire/contact/actuator/cruise dynamics differ from the Python bicycle plant.',
            'Existing tire calibration was developed at 15..25 m/s; 8 m/s is extrapolation.',
            'Actual subprocess workers; wall timing is observed engineering timing, not WCET.',
            'Known current ideal simulator sensor packet; no noisy hardware sensing claim.'])
    write(output/'protocol.json',protocol)
    for source in files:
        target=output/'source'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    return protocol


def run_case(output,case):
    out=output/case['name'];out.mkdir(exist_ok=False)
    project=out/'project';(project/'worlds').mkdir(parents=True)
    (project/'controllers').symlink_to(INTEGRATION/'controllers',target_is_directory=True)
    calibration=json.loads((INTEGRATION/'research/calibration.json').read_text())
    world=(INTEGRATION/'worlds/publication_v9.wbt').read_text().replace('../.runtime/protos',str(INTEGRATION/'.runtime/protos'))
    for axle in ('front','rear'):
        slip=4*case['speed']/80000*calibration[axle+'_slip_multiplier']
        world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
    worldpath=project/'worlds/validation.wbt';worldpath.write_text(world);(out/'generated-world.wbt').write_text(world)
    case=dict(case,output=str(out));write(out/'case.json',case)
    env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_CASE_CONFIG=str(out/'case.json'),
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='2',
        NUMBA_CACHE_DIR='/workspace/lans-setup/numba9-native',MPLCONFIGDIR='/workspace/lans-setup/mpl-native')
    started=time.monotonic()
    with (out/'console.log').open('w') as log:
        run_native(['bash',str(ROOT/'tools/cloud/run-webots.sh'),'--stdout','--stderr','--batch',
            '--mode=fast','--no-rendering',str(worldpath)],env=env,stdout=log,timeout=240)
    result=json.loads((out/'summary.json').read_text())
    write(out/'provenance.json',dict(wall_elapsed_s=time.monotonic()-started,
        world_sha256=sha(worldpath),config_sha256=sha(out/'case.json'),raw_sha256=sha(out/'ticks.jsonl'),
        native_physics=True,ego_python_integrated=False,physics_step_s=.001))
    print(case['name'],'ticks',result['ticks'],'corridor',result['corridor_exceedances'],
          'RMSE',result['rmse_m'],'response misses',result['response_misses'],flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--smoke',action='store_true');a=p.parse_args();output=a.output.resolve()
    protocol=prepare(output,a.smoke)
    results=[]
    for case in protocol['cases']:
        for name,digest in protocol['source_hashes'].items():assert sha(ROOT/name)==digest,('Native source changed',name)
        for seed,digest in protocol['policies'].items():assert sha(DATA/'policies'/f'seed-{seed}'/'policy.zip')==digest
        results.append(run_case(output,case))
    write(output/'summary.json',results)
    write(output/'STATUS.json',dict(completed=True,episodes=len(results),smoke=a.smoke,
        all_tracking_completed=all(r['completed'] and r['corridor_exceedances']==0 for r in results),
        full_framework_native_validated=False))


if __name__=='__main__':main()
