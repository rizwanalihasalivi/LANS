"""Preserve completed native outcomes; resume missing cases after warmup repair."""
from pathlib import Path
import json,shutil
from . import native
from .calibrate import write,sha


def main():
    root=native.DATA/'native-validation-v1';p=json.loads((root/'protocol.json').read_text())
    assert not (root/'STATUS.json').exists(),'Never repeat a completed cohort'
    record=root/'interruption-1';record.mkdir(exist_ok=False);completed=[];pending=[];failures=[]
    for c in p['cases']:
        out=root/c['name'];s=out/'summary.json'
        if s.exists():
            r=json.loads(s.read_text());assert sha(out/'ticks.jsonl')==r['raw_sha256'] and sha(out/'timing.jsonl')==r['timing_sha256']
            completed.append(dict(name=c['name'],summary_sha256=sha(s),raw_sha256=r['raw_sha256'],timing_sha256=r['timing_sha256']))
        else:
            if out.exists():
                assert not (out/'ticks.jsonl').exists(),'A measured failure cannot be silently repeated'
                dest=record/'failed-startup'/c['name'];dest.parent.mkdir(parents=True,exist_ok=True);out.rename(dest)
                failures.append(dict(name=c['name'],failure_path=str((dest/'failure.txt').relative_to(root)),failure_sha256=sha(dest/'failure.txt')))
            pending.append(c)
    assert len(completed)==18 and len(pending)==10 and len(failures)==1
    # Numerical controllers/actors/cases stay fixed. Only the warmup fixture and
    # evidence/runtime helpers change after the failed pre-measurement assertion.
    critical=('control.py','traffic_guard.py','quality.py','recovery.py','cbf_reference.py')
    for name in critical:
        n='tools/v8_reliability/'+name;assert sha(native.ROOT/n)==p['source_hashes'][n]
    files=[native.ROOT/name for name in p['source_hashes']];files.extend(Path(__file__).parent.glob('*.py'));files.extend(Path(__file__).parent.glob('*.md'))
    hashes={str(f.relative_to(native.ROOT)):sha(f) for f in sorted(set(files))}
    for name in hashes:
        d=record/'source'/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(native.ROOT/name,d)
    write(record/'resume-plan.json',dict(completed_preserved=completed,pending=[c['name'] for c in pending],startup_failures_retained=failures,
        source_hashes=hashes,original_protocol_sha256=sha(root/'protocol.json'),numerical_controller_changed=False,
        cause='Warmup incorrectly required an admitted plan from the actual curved route; a legitimately infeasible proposal prevented fallback from running.',
        repair='Warm returned-plan admission on a fixed feasible straight startup fixture; score the unchanged actual route after physical warmup.',
        completed_outcomes_rerun=0,measured_failed_outcomes_rerun=0))
    print('NATIVE RESUME preserved18, pending10; one failed startup retained',flush=True)
    for c in pending:
        for n,h in hashes.items():assert sha(native.ROOT/n)==h,('Source changed',n)
        native.run(root,c)
    for d in completed:
        out=root/d['name'];assert sha(out/'summary.json')==d['summary_sha256'] and sha(out/'ticks.jsonl')==d['raw_sha256'] and sha(out/'timing.jsonl')==d['timing_sha256']
    results=[json.loads((root/c['name']/'summary.json').read_text()) for c in p['cases']];native.write(root/'summary.json',results)
    new=[r for r in results if r['case']['execution']=='process']
    write(root/'STATUS.json',dict(completed=True,episodes=28,smoke=False,startup_failures_retained=1,completed_outcomes_rerun=0,
        current_tracking_pass=all(r['completed'] and r['corridor_exceedances']==0 for r in new),
        current_timing_pass=all(r['scheduled_cycle_misses']==0 and r['scheduled_response_misses']==0 for r in new),
        current_physical_rate_pass=all(r['max_measured_rate']<=.6+1e-9 for r in new),full_framework_native_validated=False))


if __name__=='__main__':main()
