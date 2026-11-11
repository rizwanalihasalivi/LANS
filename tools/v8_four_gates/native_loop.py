"""Six fixed exposed native inner-loop/GC development comparisons."""
from pathlib import Path
import json,os,shutil,hashlib
from integrations.webots.research.native_process import run_native
from .resources import choose_cpus
from .native_steps import build

ROOT=Path(__file__).resolve().parents[2];WEBOTS=ROOT/'integrations/webots';OUT=ROOT/'results/v8-four-gates/native-loop-development-v1'


def main(*,output=None,seconds=None,selected_variants=None,entry_name='native_loop_entry.py',extra_args=()):
    global OUT
    if output is not None:OUT=Path(output)
    OUT.mkdir(parents=True,exist_ok=False);library=OUT/'lans_native_steps.so';build_command=build(library)
    previous=json.loads((ROOT/'results/lans-reliability-v10/native-validation-v1/protocol.json').read_text());cpus=choose_cpus()
    names=('straight-16-process-hybrid-43','sine-8-process-hybrid-42');cases=[c for n in names for c in previous['cases'] if c['name']==n]
    if seconds is not None:cases=[dict(c,duration=seconds) for c in cases]
    variants=[dict(name='python-freeze',compiled_loop=False,freeze_gc=True),dict(name='c-loop',compiled_loop=True,freeze_gc=False),dict(name='c-loop-freeze',compiled_loop=True,freeze_gc=True)]
    if selected_variants is not None:variants=[v for v in variants if v['name'] in selected_variants]
    files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md'),*Path(__file__).parent.glob('*.c'),*Path(ROOT/'tools/v8_reliability').glob('*.py'),*Path(ROOT/'integrations/unified_lans').glob('*.py')]
    for v in range(4,10):files.extend(Path(ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'plan.json').write_text(json.dumps(dict(cases=cases,variants=variants,source_hashes=hashes,cpus=cpus,expected_runs=len(cases)*len(variants),entry_name=entry_name,extra_args=extra_args,build_command=build_command,library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),scope='exposed development only; hotspot entry adds profiling overhead'),indent=2)+'\n')
    for p in files:d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    calibration=json.loads((WEBOTS/'research/calibration.json').read_text());results=[]
    for c in cases:
        for variant in variants:
            out=OUT/(c['name']+'-'+variant['name']);out.mkdir();project=out/'project';(project/'worlds').mkdir(parents=True);entry=project/'controllers/four_gates/four_gates.py';entry.parent.mkdir(parents=True);shutil.copyfile(Path(__file__).parent/entry_name,entry)
            world=(WEBOTS/'worlds/publication_v9.wbt').read_text().replace('../.runtime/protos',str(WEBOTS/'.runtime/protos')).replace('controller "publication_v9"','controller "four_gates"')
            for axle in ('front','rear'):
                slip=4*c['speed']/80000*calibration[axle+'_slip_multiplier'];world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
            wp=project/'worlds/loop.wbt';wp.write_text(world);case=dict(c,**variant,output=str(out),native_library=str(library));(out/'case.json').write_text(json.dumps(case,indent=2)+'\n')
            env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_CASE_CONFIG=str(out/'case.json'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR='/workspace/lans-setup/mpl',NUMBA_CACHE_DIR='/workspace/lans-setup/numba-four-gates-native-loop',LP_NUM_THREADS='1',LANS_RUNTIME_CPUS=','.join(map(str,cpus)))
            command=['taskset','-c',str(cpus[1]),'bash',str(WEBOTS/'run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',*extra_args,str(wp)]
            with (out/'console.log').open('w') as log:run_native(command,env=env,stdout=log,timeout=300)
            s=json.loads((out/'summary.json').read_text());results.append(s);print(c['name'],variant['name'],'response',s['response_misses'],'scheduled cycles',s['scheduled_cycle_misses'],flush=True)
    (OUT/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
    for n,h in hashes.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h


if __name__=='__main__':main()
