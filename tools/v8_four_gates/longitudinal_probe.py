"""Fixed exposed progress/collision regressions for the continuous guard."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,hashlib,shutil,multiprocessing as mp
import numpy as np
from integrations.unified_lans.run import clean
from tools.unified_control_v9.learning import run_episode
from tools.v8_reliability import confirm as published
from tools.v8_reliability.traffic_guard import Controller as V2,Synchronous as SyncV2
from .longitudinal import Controller,Synchronous

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'results/v8-four-gates';OUT=DATA/'longitudinal-development-v1'


def write(p,v):p.write_text(json.dumps(clean(v),indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(job):
    c,freq,mode,actor=job;dest=OUT/f'{c["id"]:02d}-{freq:g}-{mode}-{actor}';dest.mkdir()
    cls=(SyncV2 if mode=='lqr' else V2) if freq==0 else Synchronous if mode=='lqr' else Controller
    kw=dict(quality_factor=1.1,early_id=True,tracking_only=False,adaptive=mode in ('adaptive','hybrid'),mpc=mode!='lqr')
    if mode!='lqr':kw['secondary_factor']=1.075
    if freq:kw['barrier_frequency']=freq
    r,rows=run_episode(c,'hybrid' if actor else 'lqr' if mode=='lqr' else 'deterministic',published.MODELS.get(actor),grid=mode!='lqr',controller_factory=cls,controller_kwargs=kw)
    raw=dest/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(x),allow_nan=False)+'\n' for x in rows))
    r.update(mode=mode,actor=actor,frequency=freq,raw_sha256=sha(raw),projection_infeasible_ticks=sum(bool(x.get('longitudinal_projection') and x['longitudinal_projection']['status']=='INFEASIBLE_FALLBACK') for x in rows),
        mean_accel_jump=float(np.mean([abs(b['issued_accel']-a['issued_accel']) for a,b in zip(rows,rows[1:])])),
        recourse_ticks=sum(x['source']=='recovery_lqr' for x in rows))
    write(dest/'summary.json',r);return r


def main():
    old=ROOT/'results/lans-reliability-v10';v1=json.loads((old/'confirmation-v1/plan.json').read_text());v2=json.loads((old/'confirmation-v2/plan.json').read_text())
    cases=[dict(c,id=i) for i,c in enumerate(v1['cases']['known_crossing'])]
    cases.append(dict(next(c for c in v1['cases']['final'] if c['id']==42),id=5,origin='exposed_v1_final42'))
    rr=json.loads((old/'confirmation-v2/final-summary.json').read_text());base={r['case']['id']:r for r in rr if r['mode']=='lqr'}
    worst=min((r for r in rr if r['mode']=='hybrid'),key=lambda r:r['progress_m']/base[r['case']['id']]['progress_m'])
    cases.append(dict(worst['case'],id=6,original_case_id=worst['case']['id'],origin='exposed_v2_progress_failure'))
    OUT.mkdir(parents=True,exist_ok=False);files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')];hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    write(OUT/'plan.json',dict(cases=cases,frequencies=[1.5,2.,3.],sources=hashes,expected_records=154,policies_changed=False,
        selector='zero hybrid failures and every-case99%matched-LQR progress, then fewest infeasible-projection ticks, then smallest mean acceleration jump, then frequency',
        scope='exposed development only; same guard for all current baselines and actors'))
    for p in files:d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    jobs=[]
    for c in cases:
        for mode in ('lqr','hybrid'):
            for actor in published.SEEDS if mode=='hybrid' else (0,):jobs.append((c,0.,mode,actor))
        for freq in (1.5,2.,3.):
            for mode in ('lqr','optimized','adaptive','hybrid'):
                for actor in published.SEEDS if mode=='hybrid' else (0,):jobs.append((c,freq,mode,actor))
    assert len(jobs)==154
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=published.initialize) as pool:
        results=[]
        for i,f in enumerate(as_completed([pool.submit(run,j) for j in jobs]),1):
            results.append(f.result())
            if i%14==0:print('CONTINUOUS GUARD',i,'/154',flush=True)
    write(OUT/'summary.json',results);scores=[]
    for f in (1.5,2.,3.):
        base={r['case']['id']:r for r in results if r['frequency']==f and r['mode']=='lqr'};rr=[r for r in results if r['frequency']==f and r['mode']=='hybrid']
        scores.append(dict(frequency=f,failures=sum(r['failed'] for r in rr),minimum_progress_ratio=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in rr),
            projection_infeasible_ticks=sum(r['projection_infeasible_ticks'] for r in rr),mean_accel_jump=float(np.mean([r['mean_accel_jump'] for r in rr]))))
    eligible=[s for s in scores if s['failures']==0 and s['minimum_progress_ratio']>=.99]
    selected=min(eligible,key=lambda s:(s['projection_infeasible_ticks'],s['mean_accel_jump'],s['frequency'])) if eligible else None
    write(OUT/'selection.json',dict(scores=scores,selected=selected));print(json.dumps(dict(scores=scores,selected=selected)),flush=True)


if __name__=='__main__':main()
