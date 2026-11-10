"""Frozen matched actual-Webots validation; single-vehicle transfer only."""
from pathlib import Path
import argparse,json,os,shutil,sys,time
from .calibrate import write,sha
from .confirm import ROOT,DATA,SEEDS
from integrations.webots.research.native_process import run_native

WEBOTS=ROOT/'integrations/webots'


def protos():
    paths=[]
    for line in (WEBOTS/'runtime-sha256.txt').read_text().splitlines():
        digest,name=line.split()
        if name.startswith('protos/'):
            path=WEBOTS/'.runtime'/name;assert sha(path)==digest,('PROTO mismatch',name);paths.append(path)
    assert len(paths)==5;return paths


def safety():
    root=DATA/'confirmation-v2'
    s=json.loads((root/'safety-summary.json').read_text())
    audit=json.loads((root/'independent-verification.json').read_text())
    assert s['current_python_safety_pass'] and audit['passed'] and audit['episodes']==1240
    return dict(report=s,independent_audit_sha256=sha(root/'independent-verification.json'),plan_sha256=sha(root/'plan.json'))


def cases(smoke):
    p=json.loads((DATA/'confirmation-v2/plan.json').read_text());selected=dict(p['arm']);selected.pop('sync')
    result=[]
    for road,speed in [('straight',10.)] if smoke else [(r,v) for r in ('straight','sine') for v in (8.,16.)]:
        roles=[('lqr',0,'sync'),('hybrid',42,'process')] if smoke else [('lqr',0,'sync'),*[(m,a,e) for m,e in [('hybrid','original-v8'),('hybrid','process')] for a in SEEDS]]
        for mode,actor,execution in roles:
            params=dict(quality_factor=1.10,early_id=True,tracking_only=False)
            if execution=='process':params.update(selected)
            result.append(dict(name=f'{road}-{speed:g}-{execution}-{mode}-{actor}',route=road,speed=speed,
                mode=mode,actor=actor,execution=execution,controller_revision=2,phase=.5 if smoke else 17.35,amplitude=1.15,
                lateral=.3,heading=.005,duration=.5 if smoke else 12.,controller_kwargs=params,
                policy=str(ROOT/f'results/python-campaign-v2/policies/seed-{actor}') if actor else None))
    assert len(result)==(2 if smoke else 28);return result


def prepare(out,smoke):
    dependencies=protos();gate=None if smoke else safety()
    out.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((DATA/'confirmation-v2/plan.json').read_text())
    files=[ROOT/name for name in frozen['source_hashes']]
    files.extend(Path(__file__).parent.glob('*.py'));files.extend(Path(__file__).parent.glob('*.md'))
    files.extend([ROOT/'tools/__init__.py',WEBOTS/'worlds/publication_v9.wbt',WEBOTS/'research/calibration.json',WEBOTS/'research/native_process.py',WEBOTS/'run-webots.sh',*dependencies])
    files=sorted(set(files));hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    p=dict(smoke=smoke,kind='engineering_smoke' if smoke else 'frozen_native_single_vehicle_comparison',
        cases=cases(smoke),python_safety=gate,source_hashes=hashes,
        policies={a:sha(ROOT/f'results/python-campaign-v2/policies/seed-{a}/policy.zip') for a in SEEDS},
        confirmation_plan_sha256=sha(DATA/'confirmation-v2/plan.json'),controller_revision=2,physics_step_s=.001,control_period_s=.05,
        deadline_ms=50.,actuator_rate_reserve=.59,physical_rate_gate=.6,
        score='whole-duration RMSE; incomplete tails penalized at 2.5m; all outcomes retained',
        limitation='Single ideal-sensor car; no native traffic/collision/communication or universal/WCET safety proof.')
    write(out/'protocol.json',p)
    for f in files:
        d=out/'source'/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
    return p


def run(out,c):
    dest=out/c['name'];dest.mkdir(exist_ok=False);project=dest/'project'
    (project/'worlds').mkdir(parents=True);entry=project/'controllers/v8_reliability/v8_reliability.py';entry.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).parent/'native_entrypoint.py',entry)
    world=(WEBOTS/'worlds/publication_v9.wbt').read_text().replace('../.runtime/protos',str(WEBOTS/'.runtime/protos')).replace('controller "publication_v9"','controller "v8_reliability"')
    cal=json.loads((WEBOTS/'research/calibration.json').read_text())
    for axle in ('front','rear'):
        slip=4*c['speed']/80000*cal[axle+'_slip_multiplier']
        world=world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',f'forceDependentSlip [ {slip} 0 ]')
    wp=project/'worlds/validation.wbt';wp.write_text(world);(dest/'generated-world.wbt').write_text(world)
    c=dict(c,output=str(dest));write(dest/'case.json',c)
    env=os.environ.copy();env.update(LANS_ROOT=str(ROOT),LANS_CASE_CONFIG=str(dest/'case.json'),
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='2',
        NUMBA_CACHE_DIR='/workspace/lans-setup/numba-v8-native',MPLCONFIGDIR='/workspace/lans-setup/mpl')
    start=time.monotonic()
    with (dest/'console.log').open('w') as log:
        run_native(['bash',str(WEBOTS/'run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(wp)],env=env,stdout=log,timeout=300)
    s=json.loads((dest/'summary.json').read_text())
    write(dest/'provenance.json',dict(world_sha256=sha(wp),entry_sha256=sha(entry),case_sha256=sha(dest/'case.json'),
        wall_elapsed_s=time.monotonic()-start,native_physics=True,ego_python_integrated=False,physics_step_s=.001))
    print(c['name'],'ticks',s['ticks'],'corridor',s['corridor_exceedances'],'response misses',s['response_misses'],'scheduled cycle misses',s['scheduled_cycle_misses'],flush=True)
    return s


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--smoke',action='store_true');a=p.parse_args();out=a.output.resolve()
    protocol=prepare(out,a.smoke);results=[]
    for c in protocol['cases']:
        for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
        for actor,h in protocol['policies'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{actor}/policy.zip')==h
        results.append(run(out,c))
    write(out/'summary.json',results)
    new=[r for r in results if r['case']['execution']=='process']
    write(out/'STATUS.json',dict(completed=True,episodes=len(results),smoke=a.smoke,
        current_tracking_pass=all(r['completed'] and r['corridor_exceedances']==0 for r in new),
        current_timing_pass=all(r['scheduled_cycle_misses']==0 and r['scheduled_response_misses']==0 for r in new),
        current_physical_rate_pass=all(r['max_measured_rate']<=.6+1e-9 for r in new),full_framework_native_validated=False))


if __name__=='__main__':main()
