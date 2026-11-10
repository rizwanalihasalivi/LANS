"""Resume unmeasured worker cases after a startup-only harness correction."""
from pathlib import Path
import json,shutil,subprocess,sys
from .confirm import ROOT,DATA
from .calibrate import write,sha


def name(i,j):return f'{i:02d}-{j["role"]}-{j["actor"]}-{j["case"]["scenario"]}-{j["ppo_fault"]}-{j["planner_fault"]}'


def main():
    root=DATA/'live-v1';p=json.loads((root/'protocol.json').read_text());assert not (root/'STATUS.json').exists()
    attempt=root/'interruption-1';attempt.mkdir(exist_ok=False);completed=[];pending=[];failures=[]
    for i,j in enumerate(p['jobs']):
        dest=root/name(i,j)
        if (dest/'summary.json').exists():
            s=json.loads((dest/'summary.json').read_text());assert sha(dest/'ticks.jsonl')==s['raw_sha256'] and sha(dest/'timing.jsonl')==s['timing_sha256']
            completed.append(dict(name=dest.name,summary_sha256=sha(dest/'summary.json'),raw_sha256=s['raw_sha256'],timing_sha256=s['timing_sha256']))
        else:
            if dest.exists():
                assert not (dest/'ticks.jsonl').exists(),'Never repeat a measured failed outcome'
                target=attempt/'failed-startup'/dest.name;target.parent.mkdir(parents=True,exist_ok=True);dest.rename(target)
                log=root/(dest.name+'.log');saved=target/'console.log';log.rename(saved)
                failures.append(dict(name=dest.name,failure_path=str(saved.relative_to(root)),failure_sha256=sha(saved)))
            pending.append((i,j))
    assert len(completed)==12 and len(pending)==14 and len(failures)==1
    for file in ('control.py','traffic_guard.py','quality.py','recovery.py','cbf_reference.py'):
        n='tools/v8_reliability/'+file;assert sha(ROOT/n)==p['source_hashes'][n]
    files=[ROOT/n for n in p['source_hashes']];files.extend(Path(__file__).parent.glob('*.py'));files.extend(Path(__file__).parent.glob('*.md'))
    hashes={str(f.relative_to(ROOT)):sha(f) for f in sorted(set(files))}
    for n in hashes:
        d=attempt/'source'/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,d)
    write(attempt/'resume-plan.json',dict(completed_preserved=completed,pending=[name(i,j) for i,j in pending],startup_failures_retained=failures,
        source_hashes=hashes,original_protocol_sha256=sha(root/'protocol.json'),numerical_controller_changed=False,
        cause='Harness required an accepted startup optimization result instead of allowing legitimate solver rejection/fallback.',
        repair='Nominal empty-road startup; explicit optional-plan cost compilation; actual solver admitted/rejected counts recorded.',
        completed_outcomes_rerun=0,measured_failed_outcomes_rerun=0))
    print('ACTUAL WORKER RESUME preserved12, unmeasured14; failed startup retained',flush=True)
    for i,j in pending:
        for n,h in hashes.items():assert sha(ROOT/n)==h,('Source changed',n)
        spec=root/f'job-{i:02d}.json'
        if not spec.exists():write(spec,dict(job=j,arm=p['arm']))
        else:assert json.loads(spec.read_text())==dict(job=j,arm=p['arm'])
        dest=root/name(i,j)
        with (root/(dest.name+'.log')).open('w') as log:
            subprocess.run([sys.executable,'-u','-m','tools.v8_reliability.live_case','--job',str(spec),'--output',str(dest)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        r=json.loads((dest/'summary.json').read_text());print('RESUMED WORKER',i+1,'/26','failed',r['failed'],'response misses',r['response_misses'],'scheduled cycle misses',r['scheduled_cycle_misses'],flush=True)
    for d in completed:
        out=root/d['name'];assert sha(out/'summary.json')==d['summary_sha256'] and sha(out/'ticks.jsonl')==d['raw_sha256'] and sha(out/'timing.jsonl')==d['timing_sha256']
    records=[json.loads((root/name(i,j)/'summary.json').read_text()) for i,j in enumerate(p['jobs'])];write(root/'summary.json',records);new=[r for r in records if r['role']=='new']
    write(root/'STATUS.json',dict(completed=True,episodes=26,startup_failures_retained=1,completed_outcomes_rerun=0,
        current_functional_pass=all(not r['failed'] and r['fault_checks_passed'] for r in new),
        current_timing_pass=all(r['scheduled_cycle_misses']==0 and r['scheduled_response_misses']==0 for r in new),policies_changed=False))


if __name__=='__main__':main()
