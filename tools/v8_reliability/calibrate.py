"""Fixed v8-based calibration; no PPO training or held-out data access."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import hashlib,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.run import clean
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v8.control import Controller as V8
from tools.unified_control_v9.learning import run_episode
from .control import Controller,Synchronous

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/lans-reliability-v10/calibration-v1'
ARMS={
    'cached-sync':dict(sync=True,quality_factor=1.10,secondary_factor=1.10),
    'async-q110-g1075':dict(sync=False,quality_factor=1.10,secondary_factor=1.075),
    'async-q105-g1075':dict(sync=False,quality_factor=1.05,secondary_factor=1.075),
    'async-q105-g105':dict(sync=False,quality_factor=1.05,secondary_factor=1.05),
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(clean(obj),indent=2,allow_nan=False)+'\n')


def prepare():
    OUT.mkdir(parents=True,exist_ok=False)
    files=[p for p in Path(__file__).parent.iterdir() if p.suffix in ('.py','.md')]
    files.extend((ROOT/'integrations/unified_lans').glob('*.py'))
    for v in range(4,10):files.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    files.extend(ROOT/n for n in ('tools/unified_campaign/study.py','controllers/lqr_controller.py','models/bicycle_model.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))}
    p=dict(arms=ARMS,cases=cases(),seconds=6.,expected_records=704,sources=hashes,
        actor_training_steps=0,base='v8 conic-v8-early-id, R16, horizon2s, mixed cost',
        protocol_sha256=sha(Path(__file__).with_name('PROTOCOL.md')))
    write(OUT/'plan.json',p)
    for name in hashes:
        dest=OUT/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return p


def check(p):
    for name,h in p['sources'].items():assert sha(ROOT/name)==h,('source changed',name)


def run(job):
    name,mode,case=job;path=OUT/f'{name}-{mode}-{case["id"]:03d}'
    path.mkdir(exist_ok=False)
    if name=='v8':cls=V8;kw=dict(quality_factor=1.10)
    elif name=='common-lqr':cls=Synchronous;kw=dict(quality_factor=1.10)
    else:
        kw=dict(ARMS[name]);cls=Synchronous if kw.pop('sync') else Controller
    kw.update(adaptive=mode=='adaptive',mpc=mode!='lqr',early_id=True,tracking_only=False)
    label='lqr' if mode=='lqr' else 'deterministic'
    result,rows=run_episode(case,label,grid=mode!='lqr',controller_factory=cls,controller_kwargs=kw)
    raw=path/'ticks.jsonl'
    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    result.update(arm=name,mode=mode,raw_sha256=sha(raw),
        recovery_ticks=sum(r['source']=='recovery_lqr' for r in rows),
        uncertified_recovery_ticks=sum(bool(r.get('recovery') and r['recovery']['mode']=='uncertified_emergency_improvement') for r in rows))
    write(path/'summary.json',result)
    return result


def assess(results):
    base={r['case']['id']:r for r in results if r['arm']=='common-lqr'}
    def metrics(name,mode):
        rr=[r for r in results if r['arm']==name and r['mode']==mode]
        return dict(heading=float(np.mean([r['heading_rms'] for r in rr])),
            rate=float(np.mean([r['rate_rms'] for r in rr])),rmse=float(np.mean([r['rmse_m'] for r in rr])))
    reference={m:metrics('v8',m) for m in ('optimized','adaptive')}
    scores=[]
    for name in ARMS:
        rr=[r for r in results if r['arm']==name];ratios={}
        for mode in ('optimized','adaptive'):
            actual=metrics(name,mode);old=reference[mode]
            ratios[mode]=dict(v8_heading_ratio=actual['heading']/old['heading'],v8_rate_ratio=actual['rate']/old['rate'],**actual)
        q=all(r['v8_heading_ratio']<=1.+1e-12 and r['v8_rate_ratio']<=1.+1e-12 for r in ratios.values())
        improved=min(v for r in ratios.values() for k,v in r.items() if k.startswith('v8_'))<=.99
        rmse=float(np.mean([r['rmse_m'] for r in rr]));oldrmse=np.mean([r['rmse'] for r in reference.values()])
        h=max(np.mean([r['heading_rms'] for r in rr if r['mode']==mode])/np.mean([r['heading_rms'] for r in base.values()]) for mode in ratios)
        rate=max(np.mean([r['rate_rms'] for r in rr if r['mode']==mode])/np.mean([r['rate_rms'] for r in base.values()]) for mode in ratios)
        progress=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in rr)
        eligible=not any(r['failed'] for r in rr) and h<=1.10 and rate<=1.10 and progress>=.99
        scores.append(dict(arm=name,eligible=bool(eligible),quality_repair=bool(q and improved and rmse<=1.01*oldrmse),
            rmse_m=rmse,heading_ratio=float(h),rate_ratio=float(rate),minimum_progress_ratio=float(progress),by_mode=ratios,
            failures=sum(r['failed'] for r in rr)))
    pool=[s for s in scores if s['eligible'] and s['quality_repair']] or [s for s in scores if s['eligible']]
    selected=min(pool,key=lambda r:(r['rmse_m'],r['arm'])) if pool else None
    return dict(selected=selected,scores=scores,original_v8=reference)


def main():
    p=prepare();jobs=[('common-lqr','lqr',c) for c in p['cases']]
    jobs += [(name,mode,c) for name in ['v8',*ARMS] for mode in ('optimized','adaptive') for c in p['cases']]
    assert len(jobs)==704;results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs]):
            r=f.result();results.append(r)
            if len(results)%16==0:print('V8 RELIABILITY CALIBRATION',len(results),'/704',flush=True)
    check(p);results.sort(key=lambda r:(r['arm'],r['mode'],r['case']['id']))
    write(OUT/'summary.json',results);selection=assess(results);write(OUT/'selection.json',selection)
    print(json.dumps(selection),flush=True)


if __name__=='__main__':main()
