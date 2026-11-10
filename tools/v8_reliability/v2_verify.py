"""Independent V2 trajectory reconstruction and unchanged scientific gates."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import argparse,json
from .verify import episode,sha
from .summarize import assess
from .calibrate import write
from .confirm import DATA,SEEDS,MODES,ACTOR_MODES


def exposed():
    root=DATA/'v2-exposed-development';p=json.loads((root/'plan.json').read_text());jobs=[]
    for name,h in p['source_hashes'].items():assert sha(root/'source'/name)==h
    for c in p['cases']:
        for m in ('lqr','optimized','adaptive','hybrid','v8_original'):
            for a in SEEDS if m in ACTOR_MODES else (0,):jobs.append((root/f'{c["id"]:03d}-{m}-{a}',c,m,a,'v2_exposed',sha(root/'plan.json')))
    assert len(jobs)==54 and {j[0]/'summary.json' for j in jobs}==set(root.glob('*/summary.json'))
    with ProcessPoolExecutor(max_workers=4) as pool:rr=list(pool.map(episode,jobs))
    report=dict(passed=True,episodes=54,ticks=sum(r['ticks'] for r in rr),scope='independent scalar dynamics, initial/NPC states, regenerated wire/freshness, FIFO, limits and whole-run metrics; exposed development only')
    write(root/'independent-verification.json',report);print(json.dumps(report),flush=True)


def confirmation():
    root=DATA/'confirmation-v2';p=json.loads((root/'plan.json').read_text());s=json.loads((root/'STATUS.json').read_text())
    assert s['completed'] and s['episodes']==1240 and s['final_once_complete']
    jobs=[];all_records=[]
    for name,h in p['source_hashes'].items():assert sha(root/'source'/name)==h
    for stage,cases in p['cases'].items():
        for c in cases:
            for m in MODES if stage=='final' else ('lqr','optimized','adaptive','hybrid','v8_original'):
                for a in SEEDS if m in ACTOR_MODES else (0,):jobs.append((root/stage/f'{c["id"]:03d}-{m}-{a}',c,m,a,stage,sha(root/'plan.json')))
        rr=json.loads((root/(stage+'-summary.json')).read_text());all_records.extend(rr)
        saved=[json.loads((j[0]/'summary.json').read_text()) for j in jobs if j[4]==stage]
        order=lambda r:(r['case']['id'],r['mode'],r['actor'])
        assert sorted(rr,key=order)==sorted(saved,key=order)
        if stage=='final':write(root/'final-assessment.json',assess(rr,p['bootstrap_seed']))
    assert len(jobs)==len(all_records)==1240 and {j[0]/'summary.json' for j in jobs}==set(root.glob('*/*/summary.json'))
    with ProcessPoolExecutor(max_workers=4) as pool:rr=list(pool.map(episode,jobs))
    report=dict(passed=True,episodes=1240,ticks=sum(r['ticks'] for r in rr),
        scope='independent scalar RK4, exact initial/NPC states, regenerated wire/freshness, command FIFO, physical limits, raw hashes/coverage and whole-run metrics; no universal/native safety proof')
    write(root/'independent-verification.json',report)
    current=[r for r in all_records if r['mode']=='hybrid']
    safety=dict(current_python_safety_pass=all(not r['failed'] for r in current),current_hybrid_episodes=len(current),
        current_hybrid_failures=sum(r['failed'] for r in current),current_hybrid_collision_ticks=sum(r['collisions'] for r in current),
        current_hybrid_recourse_ticks=sum(r['recourse_ticks'] for r in current),
        current_hybrid_uncertified_recourse_ticks=sum(r['uncertified_recourse_ticks'] for r in current),
        original_v8_failures=sum(r['failed'] for r in all_records if r['mode']=='v8_original'),
        policies_changed=False,scope='Finite six-second cases, 50ms collision samples, not universal safety or a substitute for scientific quality/progress gates.')
    write(root/'safety-summary.json',safety);print(json.dumps(dict(audit=report,safety=safety)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exposed-only',action='store_true');a=p.parse_args()
    exposed()
    if not a.exposed_only:confirmation()


if __name__=='__main__':main()
