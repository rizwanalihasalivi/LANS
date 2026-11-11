"""Eight fixed exposed native kernel/resource development comparisons."""
from pathlib import Path
import json,os,shutil,hashlib
from integrations.webots.research.native_process import run_native
from .resources import choose_cpus

ROOT=Path(__file__).resolve().parents[2];WEBOTS=ROOT/'integrations/webots';OUT=ROOT/'results/v8-four-gates/native-ablation-v1'


def main():
    OUT.mkdir(parents=True,exist_ok=False);previous=json.loads((ROOT/'results/lans-reliability-v10/native-validation-v1/protocol.json').read_text());cpus=choose_cpus()
    names=('straight-16-process-hybrid-43','sine-8-process-hybrid-42');cases=[c for n in names for c in previous['cases'] if c['name']==n]
    variants=[dict(name='base',fast_kernel=False,resources=False),dict(name='fast',fast_kernel=True,resources=False),dict(name='resources',fast_kernel=False,resources=True),dict(name='fast-resources',fast_kernel=True,resources=True)]
    files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md'),*Path(ROOT/'tools/v8_reliability').glob('*.py')];hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'plan.json').write_text(json.dumps(dict(cases=cases,variants=variants,source_hashes=hashes,cpus=cpus,expected_runs=8,scope='exposed development ablation only'),indent=2)+'\n')
    for p in files:d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    calibration=json.loads((WEBOTS/'research/calibration.json').read_text());results=[]
    for c in cases:
        for variant in variants:
            out=OUT/(c['name']+'-'+variant['name']);out.mkdir();project=out/'project';(project/'worlds').mkdir(parents=True);entry=project/'controllers/four_gates/four_gates.py';entry.parent.mkdir(parents=True);shutil.copyfile(Path(__file__).parent/'native_ablation_entry.py',entry)
            world=(WEBOTS/'worlds/publication_v9.wbt').read_text().replace('../.runtime/protos',str(WEBOTS/'.runtime/protos')).replace('controller "publication_v9"','controller "four_gates"')
            for axle in ('front','rear'):
                slip=4*c['speed']/80000*calibration[axle+'_slip_multiplier'];world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
            wp=project/'worlds/ablation.wbt';wp.write_text(world);case=dict(c,**variant,output=str(out));(out/'case.json').write_text(json.dumps(case,indent=2)+'\n')
            env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_CASE_CONFIG=str(out/'case.json'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR='/workspace/lans-setup/mpl',NUMBA_CACHE_DIR='/workspace/lans-setup/numba-four-gates-native-ablation')
            command=['bash',str(WEBOTS/'run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(wp)]
            if variant['resources']:env.update(LP_NUM_THREADS='1',LANS_RUNTIME_CPUS=','.join(map(str,cpus)));command=['taskset','-c',str(cpus[1]),*command]
            with (out/'console.log').open('w') as log:run_native(command,env=env,stdout=log,timeout=300)
            s=json.loads((out/'summary.json').read_text());results.append(s)
            print(c['name'],variant['name'],'response',s['response_misses'],'scheduled cycles',s['scheduled_cycle_misses'],flush=True)
    (OUT/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
    for n,h in hashes.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h


if __name__=='__main__':main()
