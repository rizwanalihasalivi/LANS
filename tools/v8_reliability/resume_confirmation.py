"""Resume only missing frozen jobs after an infrastructure/JIT-cache interruption.

Never reruns a completed outcome, changes a fixture, relaxes a gate or updates
the selected controller. Abandoned partial directories are retained separately.
Use a fresh NUMBA_CACHE_DIR dedicated to package-qualified campaign imports.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,multiprocessing as mp,os
from . import confirm as campaign
from .calibrate import sha,write


def main():
    root=campaign.OUT;p=json.loads((root/'plan.json').read_text())
    assert not (root/'STATUS.json').exists(),'Do not resume or repeat completed confirmation'
    for name,h in p['sources'].items():assert sha(campaign.ROOT/name)==h,('Frozen execution source changed',name)
    attempts=root/'interruption-1';attempts.mkdir(exist_ok=False)
    jobs=[];completed=[];partials=[]
    for stage,fixtures in p['cases'].items():
        modes=campaign.MODES if stage in ('development','final','v8_reserved') else ('lqr','optimized','adaptive','hybrid','v8_original')
        for c in fixtures:
            for mode in modes:
                for actor in campaign.SEEDS if mode in campaign.ACTOR_MODES else (0,):
                    path=root/stage/f'{c["id"]:03d}-{mode}-{actor}'
                    summary=path/'summary.json'
                    if summary.exists():
                        r=json.loads(summary.read_text());assert r['plan_sha256']==sha(root/'plan.json') and r['raw_sha256']==sha(path/'ticks.jsonl')
                        completed.append(dict(path=str(path.relative_to(root)),summary_sha256=sha(summary),raw_sha256=r['raw_sha256']))
                    else:
                        if path.exists():
                            dest=attempts/'partial-directories'/stage/path.name;dest.parent.mkdir(parents=True,exist_ok=True);path.rename(dest);partials.append(str(dest.relative_to(root)))
                        jobs.append((stage,c,mode,actor))
    assert len(completed)+len(jobs)==p['expected_records']==2309
    write(attempts/'resume-plan.json',dict(cause="Numba cached environment imported top-level v8_reliability after pytest collection; campaign imports tools.v8_reliability. Infrastructure exception, not a completed controller outcome.",
        exception="ModuleNotFoundError: No module named 'v8_reliability'",completed_preserved=completed,
        pending=[dict(stage=s,case_id=c['id'],mode=m,actor=a) for s,c,m,a in jobs],partial_directories=partials,
        cache_directory=os.environ.get('NUMBA_CACHE_DIR'),plan_sha256=sha(root/'plan.json'),controller_changed=False,fixtures_changed=False))
    print('RESUME FROZEN CONFIRMATION preserved',len(completed),'missing',len(jobs),flush=True)
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=campaign.initialize) as pool:
        for i,f in enumerate(as_completed([pool.submit(campaign.run,j) for j in jobs]),1):
            f.result()
            if i%16==0:print('RESUMED',i,'/',len(jobs),flush=True)
    for name,h in p['sources'].items():assert sha(campaign.ROOT/name)==h,('Frozen source changed',name)
    for r in completed:
        path=root/r['path'];assert sha(path/'summary.json')==r['summary_sha256'] and sha(path/'ticks.jsonl')==r['raw_sha256']
    total=0
    for stage in p['cases']:
        rr=[json.loads(path.read_text()) for path in (root/stage).glob('*/summary.json')];total+=len(rr)
        rr.sort(key=lambda r:(r['case']['id'],r['mode'],r['actor']));write(root/(stage+'-summary.json'),rr)
    assert total==2309
    write(root/'STATUS.json',dict(complete=True,episodes=total,training_steps=0,policies_changed=False,
        infrastructure_interruptions=1,completed_records_rerun=0,original_plan_retained=True))


if __name__=='__main__':main()
