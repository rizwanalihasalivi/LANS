"""Native interface campaign with exported PPO and the shared supervisor."""
import common
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from native_process import run_native

INTEGRATION=common.ROOT/'integrations/webots'


def digest(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True)
    args=p.parse_args();args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    definitions=[('dlc20',20,'dlc220',(1,0.,0.,0.),0),
                 ('sine15',15,'sine120',(0,2.5,120.,.3),0),
                 ('dlc25_delay100',25,'dlc220',(1,0.,0.,0.),100)]
    sources=[Path(__file__),common.HERE/'supervisor.py',common.HERE/'runtime_adapter.py',
             INTEGRATION/'controllers/reviewer_validation/reviewer_validation.py',
             INTEGRATION/'research/causal_runtime.py',common.ROOT/'tools/controller_review/realtime_causal.py']
    protocol=dict(kind='Native PPO-export interface development, not performance promotion',smoke=False,
        source_hashes={str(f.relative_to(common.ROOT)):digest(f) for f in sources},
        model_hashes={name:digest(args.models/'701'/name) for name in ('student.pt','normalization.npz','complete.json')},
        policy_origin='25k causal PPO export; causal_student mode is legacy interface label',
        methods=['lqr','causal_student'],definitions=definitions)
    (args.output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    calibration=json.loads((INTEGRATION/'research/calibration.json').read_text())
    results=[]
    for name,speed,path,parameters,delay in definitions:
        for mode in ('lqr','causal_student'):
            out=args.output/f'{name}-{mode}';out.mkdir()
            project=INTEGRATION/'.runtime/native-cases'/hashlib.sha256(str(out).encode()).hexdigest()[:20]
            (project/'worlds').mkdir(parents=True,exist_ok=False)
            (project/'controllers').symlink_to(INTEGRATION/'controllers',target_is_directory=True)
            world=(INTEGRATION/'worlds/research_validation.wbt').read_text().replace('../.runtime/protos',str(INTEGRATION/'.runtime/protos'))
            world=world.replace('controller "research_validation"','controller "reviewer_validation"')
            for axle in ('front','rear'):
                slip=4*speed/80000*calibration[axle+'_slip_multiplier']
                world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
            worldfile=project/'worlds/test.wbt';worldfile.write_text(world)
            (out/'generated-world.wbt').write_text(world)
            case=dict(speed=speed,path=path,path_parameters=parameters,delay_ms=delay,
                seed=1076000000+speed,mode=mode,output=str(out),duration=220/speed+2,
                noise=1.,sensor_delay_steps=0,gate_config={'horizon_steps':20,'relative_margin':.01},
                policy=str((args.models/'701').resolve()))
            config=out/'case.json';config.write_text(json.dumps(case,indent=2)+'\n')
            env=os.environ.copy();env.update(LANS_INTEGRATION_ROOT=str(INTEGRATION),LANS_CASE_CONFIG=str(config),
                PATH=str(Path(os.sys.executable).parent)+':'+env['PATH'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
                NUMBA_CACHE_DIR='/tmp/lans-campaign-numba',MPLCONFIGDIR='/tmp/lans-campaign-mpl')
            start=time.time()
            with (out/'console.log').open('w') as handle:
                run_native(['bash',str(INTEGRATION/'run-gated-webots.sh'),'--stdout','--stderr','--batch',
                            '--mode=realtime','--no-rendering',str(worldfile)],env=env,stdout=handle,timeout=300)
            metrics=json.loads((out/'metrics.json').read_text());results.append(metrics)
            (out/'provenance.json').write_text(json.dumps(dict(wall_elapsed_s=time.time()-start,
                world_sha256=digest(worldfile),telemetry_sha256=digest(out/'telemetry.csv'),
                config_sha256=digest(config),mode='native Webots software actuation; not physical hardware'),indent=2)+'\n')
            print(out.name,'survived',metrics['survived'],'deadline misses',metrics['native_deadline_misses'],flush=True)
    (args.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':main()
