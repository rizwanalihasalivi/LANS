"""Two exposed actual-native timing diagnostics; no performance promotion."""
from pathlib import Path
import json,os,shutil,time,hashlib
from integrations.webots.research.native_process import run_native

ROOT=Path(__file__).resolve().parents[2];WEBOTS=ROOT/'integrations/webots';OUT=ROOT/'results/v8-four-gates/native-phase-diagnostics-v1'


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    old=json.loads((ROOT/'results/lans-reliability-v10/native-validation-v1/protocol.json').read_text())
    chosen=['straight-16-original-v8-hybrid-43','sine-8-process-hybrid-42'];cases=[c for n in chosen for c in old['cases'] if c['name']==n]
    files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md'),*Path(ROOT/'tools/v8_reliability').glob('*.py')]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'plan.json').write_text(json.dumps(dict(cases=cases,sources=hashes,scope='exposed development diagnostics; instrumentation overhead; not a fresh validation or timing pass',gc_policy='unchanged default; observe only'),indent=2)+'\n')
    for f in files:d=OUT/'source'/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
    calibration=json.loads((WEBOTS/'research/calibration.json').read_text())
    for c in cases:
        out=OUT/c['name'];out.mkdir();project=out/'project';(project/'worlds').mkdir(parents=True);entry=project/'controllers/profile_four_gates/profile_four_gates.py';entry.parent.mkdir(parents=True)
        shutil.copyfile(Path(__file__).parent/'profile_native_entry.py',entry)
        world=(WEBOTS/'worlds/publication_v9.wbt').read_text().replace('../.runtime/protos',str(WEBOTS/'.runtime/protos')).replace('controller "publication_v9"','controller "profile_four_gates"')
        for axle in ('front','rear'):
            slip=4*c['speed']/80000*calibration[axle+'_slip_multiplier'];world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
        wp=project/'worlds/profile.wbt';wp.write_text(world);case=dict(c,output=str(out));(out/'case.json').write_text(json.dumps(case,indent=2)+'\n')
        env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_CASE_CONFIG=str(out/'case.json'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_CACHE_DIR='/workspace/lans-setup/numba-four-gates-native-profile',MPLCONFIGDIR='/workspace/lans-setup/mpl')
        with (out/'console.log').open('w') as log:run_native(['bash',str(WEBOTS/'run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(wp)],env=env,stdout=log,timeout=360)
        print('PROFILE COMPLETE',c['name'],flush=True)
    for n,h in hashes.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h


if __name__=='__main__':main()
