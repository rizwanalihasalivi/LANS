"""Fixed development native Webots interface campaign; no reserved grid is opened."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2];INTEGRATION=ROOT/'integrations/webots'
sys.path.insert(0,str(INTEGRATION/'research'))
from native_process import run_native


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run_case(output,name,case,model_root,seconds=None):
    out=output/name;out.mkdir()
    project=INTEGRATION/'.runtime/native-cases'/hashlib.sha256(str(out).encode()).hexdigest()[:20]
    (project/'worlds').mkdir(parents=True,exist_ok=False)
    (project/'controllers').symlink_to(INTEGRATION/'controllers',target_is_directory=True)
    calibration=json.loads((INTEGRATION/'research/calibration.json').read_text())
    world=(INTEGRATION/'worlds/research_validation.wbt').read_text().replace('../.runtime/protos',str(INTEGRATION/'.runtime/protos'))
    world=world.replace('controller "research_validation"','controller "causal_validation"')
    for key in ('front','rear'):
        slip=4*case['speed']/80000*calibration[key+'_slip_multiplier']
        world=world.replace(f'forceDependentSlip [ 0 0 ] # {key.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
    path=project/'worlds/test.wbt';path.write_text(world);(out/'generated-world.wbt').write_text(world)
    case=dict(case,output=str(out),duration=seconds or (220/case['speed']+2),
        noise=1.,sensor_delay_steps=0,gate_config={'horizon_steps':20,'relative_margin':.01},
        policy=str((model_root/'701').resolve()))
    config=out/'case.json';config.write_text(json.dumps(case,indent=2)+'\n')
    env=os.environ.copy();env.update(LANS_INTEGRATION_ROOT=str(INTEGRATION),LANS_CASE_CONFIG=str(config),
        PATH='/workspace/lans-venv/bin:'+env['PATH'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        NUMBA_CACHE_DIR='/tmp/lans-native-v3-numba',MPLCONFIGDIR='/tmp/lans-native-v3-mpl')
    started=time.time()
    with (out/'console.log').open('w') as log:
        run_native(['bash',str(INTEGRATION/'run-gated-webots.sh'),'--stdout','--stderr','--batch',
            '--mode=realtime','--no-rendering',str(path)],env=env,stdout=log,timeout=240)
    result=json.loads((out/'metrics.json').read_text())
    (out/'provenance.json').write_text(json.dumps(dict(wall_elapsed_s=time.time()-started,
        world_sha256=digest(path),telemetry_sha256=digest(out/'telemetry.csv'),
        config_sha256=digest(config),mode='native Webots R2025a realtime mode; software actuation only'),indent=2)+'\n')
    print(name,'survived:',result['survived'],'misses:',result['native_deadline_misses'],flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    definitions=[('dlc20_nominal',20,'dlc220',(1,0.,0.,0.),0),
        ('sine15_nominal',15,'sine120',(0,2.5,120.,.3),0),
        ('dlc25_delay100',25,'dlc220',(1,0.,0.,0.),100)]
    if a.smoke:definitions=definitions[:1]
    sources=[INTEGRATION/'controllers/causal_validation/causal_validation.py',
        INTEGRATION/'research/causal_runtime.py',ROOT/'tools/controller_review/realtime_kernels.py',
        ROOT/'tools/controller_review/causal_student.py',Path(__file__)]
    protocol=dict(kind='development native interface only, not frozen final comparison',smoke=a.smoke,
        source_hashes={str(x.relative_to(ROOT)):digest(x) for x in sources},
        model_hashes={n:digest(a.models/'701'/n) for n in ('student.pt','normalization.npz','complete.json')},
        definitions=definitions,methods=['lqr','causal_student'],mode='realtime',
        criterion='all cases survive, finite/bounded telemetry, no stale/late learned authority or worker error; wall timing assessed separately and never claimed from simulation time')
    (a.output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    rows=[]
    for name,speed,path,parameters,delay in definitions:
        for mode in ('lqr','causal_student'):
            case=dict(speed=speed,path=path,path_parameters=parameters,delay_ms=delay,
                seed=985000000+speed,mode=mode)
            rows.append(run_case(a.output,name+'-'+mode,case,a.models,seconds=.5 if a.smoke else None))
    (a.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
