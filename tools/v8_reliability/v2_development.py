"""Fixed exposed supervision regressions; no fresh V2 promotion by assumption."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,multiprocessing as mp,shutil
from integrations.unified_lans.run import clean
from tools.unified_control_v9.learning import run_episode
from tools.unified_control_v8.control import Controller as V8
from . import confirm as campaign
from .traffic_guard import Controller,Synchronous
from .calibrate import write,sha

OUT=campaign.DATA/'v2-exposed-development'


def run(job):
    c,mode,actor=job;p=json.loads((OUT/'plan.json').read_text());dest=OUT/f'{c["id"]:03d}-{mode}-{actor}';dest.mkdir()
    cls=V8 if mode=='v8_original' else Synchronous if mode=='lqr' else Controller
    kw=dict(quality_factor=1.1,early_id=True,tracking_only=False,adaptive=mode in ('adaptive','hybrid','v8_original'),mpc=mode!='lqr')
    if cls is Controller:kw.update(p['arm']);kw.pop('sync')
    label='hybrid' if actor else 'lqr' if mode=='lqr' else 'deterministic'
    r,rows=run_episode(c,label,campaign.MODELS.get(actor),grid=mode!='lqr',controller_factory=cls,controller_kwargs=kw)
    raw=dest/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(x),allow_nan=False)+'\n' for x in rows))
    r.update(mode=mode,actor=actor,stage='v2_exposed',raw_sha256=sha(raw),plan_sha256=sha(OUT/'plan.json'),
        recourse_ticks=sum(x['source']=='recovery_lqr' for x in rows),
        uncertified_recourse_ticks=sum(bool(x.get('recovery') and x['recovery']['mode']=='uncertified_emergency_improvement') for x in rows))
    write(dest/'summary.json',r);return r


def main():
    source=campaign.DATA/'confirmation-v1';p=json.loads((source/'plan.json').read_text());cases=p['cases']['known_crossing']
    exposed=next(c for c in p['cases']['final'] if c['id']==42)
    cases=[*cases,dict(exposed,id=5,original_id=42,stage='exposed_v1_final_progress_regression')]
    OUT.mkdir(exist_ok=False);files=[campaign.ROOT/name for name in p['sources']];files.extend(Path(__file__).parent.glob('*.py'));files.extend(Path(__file__).parent.glob('*.md'))
    hashes={str(f.relative_to(campaign.ROOT)):sha(f) for f in sorted(set(files))}
    write(OUT/'plan.json',dict(cases=cases,arm=p['arm'],source_hashes=hashes,expected_records=54,policies_changed=False,exposed_only=True))
    for name in hashes:
        d=OUT/'source'/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(campaign.ROOT/name,d)
    # Explicit construction avoids counting analytical roles as actor replicates.
    jobs=[]
    for c in cases:
        for m in ('lqr','optimized','adaptive','hybrid','v8_original'):
            for a in campaign.SEEDS if m in ('hybrid','v8_original') else (0,):jobs.append((c,m,a))
    assert len(jobs)==54
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=campaign.initialize) as pool:
        results=[f.result() for f in as_completed([pool.submit(run,j) for j in jobs])]
    for name,h in hashes.items():assert sha(campaign.ROOT/name)==h
    results.sort(key=lambda r:(r['case']['id'],r['mode'],r['actor']));write(OUT/'summary.json',results)
    base={r['case']['id']:r for r in results if r['mode']=='lqr'};current=[r for r in results if r['mode']=='hybrid']
    result=dict(completed=True,episodes=54,current_failure_count=sum(r['failed'] for r in current),
        current_minimum_progress_ratio=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in current),
        current_collisions=sum(r['collisions'] for r in current),
        exposed_progress_case_ratios={r['actor']:r['progress_m']/base[5]['progress_m'] for r in current if r['case']['id']==5})
    result['development_pass']=not result['current_failure_count'] and result['current_minimum_progress_ratio']>=.99
    write(OUT/'STATUS.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
