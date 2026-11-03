"""Explicit 300 m native operating profile; original 150 m evidence stays intact."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback
from integrations.connected_v2v.autonomy.study import ROOT,write,digest
from .native import configuration,verify,DEV_SEEDS
from .scenarios import NATIVE_CASES
from .world import prepare
from .study import runtime_files,freeze,verify_sources

VALIDATION_SEEDS=(3001,3011,3019)


def prepare_coverage(output,config):
    world=prepare(output,config)
    old=world.read_text();expected=len(config['starts'])
    assert old.count('range 150')==expected
    updated=old.replace('range 150','range 300')
    assert updated.replace('range 300','range 150')==old
    world.write_text(updated)
    controller=Path(output)/'project/controllers/robust_vehicle/robust_vehicle.py'
    old=controller.read_text();assert old.count('emitter.setRange(150.)')==1
    updated=old.replace('emitter.setRange(150.)','emitter.setRange(300.)')
    assert updated.replace('emitter.setRange(300.)','emitter.setRange(150.)')==old
    compile(updated,'robust_vehicle.py','exec');controller.write_text(updated)
    return world


def run_one(job):
    output,case,speed,seed=job;output=Path(output).resolve()
    try:
        spec=configuration(case,speed,seed);spec['radio_range_m']=300.
        world=prepare_coverage(output,spec);write(output/'config.json',spec)
        write(output/'provenance.json',dict(world_sha256=digest(world),
            controller_sha256=digest(output/'project/controllers/robust_vehicle/robust_vehicle.py'),
            operating_envelope='300 m native Emitter; unchanged control, 120 m Radar, original TTLs'))
        env=os.environ.copy();env.update(LANS_V2V_REPO=str(ROOT),LANS_ROBUST_OUTPUT=str(output),
            PATH='/workspace/lans-venv/bin:'+env.get('PATH',''),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        with (output/'console.log').open('x') as log:
            subprocess.run(['bash',str(ROOT/'integrations/webots/run-webots.sh'),'--batch','--mode=fast',
                '--no-rendering','--stdout','--stderr',str(world)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        result=verify(output);result['radio_range_m']=300.
        write(output/'verification.json',result);return result
    except Exception:
        output.mkdir(parents=True,exist_ok=True);(output/'failure.txt').write_text(traceback.format_exc())
        return dict(passed=False,case=case,speed=speed,seed=seed,error='see failure.txt',radio_range_m=300.)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',required=True);p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=('development','validation'),required=True);a=p.parse_args()
    python=Path(a.python);root=Path(a.output).resolve()
    assert json.loads((python/'validation/summary.json').read_text())['passed'],'Python validation failed'
    verify_sources(json.loads((python/'plan.json').read_text())['sources'])
    if a.stage=='development':
        root.mkdir(parents=True,exist_ok=False)
        hashes=freeze(root,[*runtime_files(),*[Path(__file__).with_name(n+'.py') for n in ('native','native_vehicle','world','coverage')]])
        write(root/'plan.json',dict(cases=NATIVE_CASES,development_seeds=DEV_SEEDS,validation_seeds=VALIDATION_SEEDS,
            sources=hashes,radio_range_m=300.,python_plan_sha256=digest(python/'plan.json')))
        shutil.copyfile(Path(__file__).with_name('COVERAGE_PROTOCOL.md'),root/'PROTOCOL.md')
    plan=json.loads((root/'plan.json').read_text());verify_sources(plan['sources'])
    if a.stage=='validation':assert json.loads((root/'development/summary.json').read_text())['passed'],'300 m development failed'
    subprocess.run(['sha256sum','-c','../runtime-sha256.txt'],cwd=ROOT/'integrations/webots/.runtime',check=True)
    stage=root/a.stage;stage.mkdir(exist_ok=False)
    seeds=DEV_SEEDS if a.stage=='development' else VALIDATION_SEEDS;speeds=(8.,) if a.stage=='development' else (8.,12.)
    jobs=[(str(stage/f'{case}-{speed:g}-{seed}'),case,speed,seed) for case,speed,seed in itertools.product(NATIVE_CASES,speeds,seeds)]
    results=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run_one,j) for j in jobs]):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
    verify_sources(plan['sources']);results.sort(key=lambda r:(r['case'],r['speed'],r['seed']))
    write(stage/'summary.json',dict(passed=all(r['passed'] for r in results),results=results,radio_range_m=300.))


if __name__=='__main__':main()
