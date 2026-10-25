"""Five new-policy native interface checks; not a native performance comparison."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'research'))
from native_process import run_native
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
SOURCES=['research/core.py','research/protocol.json','research/comparison.py','research/comparison-protocol.json','research/tracking.py','research/tracking-protocol.json','research/native_process.py','research/worker.py','research/calibration.json','research/revision2/gating.py','controllers/gated_validation/gated_validation.py','controllers/range_matched_validation/range_matched_validation.py','worlds/research_validation.wbt','run-gated-webots.sh','research/revision3/native_smoke.py','research/revision3/mapping.py','research/revision3/protocol.json','results/revision2-development/freeze.json']
def run(case,name,output,source_hashes):
    destination=output/name;destination.mkdir()
    project=ROOT/'.runtime/range-matched-cases'/hashlib.sha256(str(destination).encode()).hexdigest()[:20]
    (project/'worlds').mkdir(parents=True,exist_ok=False)
    (project/'controllers').symlink_to(ROOT/'controllers',target_is_directory=True)
    calibration=json.loads((ROOT/'research/calibration.json').read_text())
    case=dict(case,output=str(destination))
    case['front_slip']=4*case['speed']/80000*calibration['front_slip_multiplier']/case['contact_scale']
    case['rear_slip']=4*case['speed']/80000*calibration['rear_slip_multiplier']/case['contact_scale']
    world=(ROOT/'worlds/research_validation.wbt').read_text().replace('../.runtime/protos',str(ROOT/'.runtime/protos'))
    world=world.replace('controller "research_validation"','controller "range_matched_validation"')
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
        run_native(['bash',str(ROOT/'run-gated-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(world_path)],env=env,stdout=log,timeout=360)
    metrics=json.loads((destination/'metrics.json').read_text())
    assert metrics['case']==case
    provenance=dict(started_unix_s=started,elapsed_wall_s=time.time()-started,python=python,source_sha256=source_hashes,
                    generated_world_sha256=sha(destination/'generated-world.wbt'),config_sha256=sha(config),telemetry_sha256=sha(destination/'telemetry.csv'),metrics_sha256=sha(destination/'metrics.json'))
    (destination/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(name,metrics['survived'],metrics['penalized_rmse_m'],flush=True)
    return name,metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--training',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    freeze=json.loads((ROOT/'results/revision2-development/freeze.json').read_text())
    for name,digest in freeze['source_sha256'].items():assert sha(ROOT/'research'/name)==digest
    sources={n:sha(ROOT/n) for n in SOURCES}
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    for n in SOURCES:
        target=output/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/n).read_bytes())
    (output/'start.json').write_text(json.dumps(dict(source_sha256=sources,phase='interface_smoke_only'),indent=2)+'\n')
    results={}
    for seed in range(5):
        policy=(args.training/f'residual-{seed}/policy.zip').resolve()
        meta=json.loads((policy.parent/'complete.json').read_text())
        assert meta['steps']==1000000 and meta['residual_scale_rad']==.08 and sha(policy)==meta['policy_sha256']
        case=dict(mode='gated_residual',speed=20,path='dlc220',seed=3910000+seed,policy_seed=seed,scenario='nominal',duration=13.,noise=1,sensor_delay_steps=0,delay_ms=0,contact_scale=1.,mu=.9,gate_config=freeze['selected_config'],policy=str(policy),policy_sha256=sha(policy))
        name=f'matched-seed{seed}-v20';name,metrics=run(case,name,output,sources);results[name]=metrics
    assert sources=={n:sha(ROOT/n) for n in SOURCES}
    (output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
    (output/'complete.json').write_text(json.dumps(dict(cases=5,summary_sha256=sha(output/'summary.json'),source_sha256=sources),indent=2)+'\n')
if __name__=='__main__':main()
