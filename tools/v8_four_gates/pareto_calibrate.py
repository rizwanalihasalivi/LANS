"""Fixed training-only strict-Pareto admission calibration; no PPO work."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,hashlib,shutil,multiprocessing as mp
import numpy as np
from integrations.unified_lans.run import clean
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v9.learning import run_episode
from .longitudinal import Synchronous as Reference
from .pareto import Controller

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/v8-four-gates/pareto-calibration-v1'
ARMS={f'h{h:g}-cap{f:g}':dict(planning_horizon=h,planner_factor=f) for h in (2.,3.) for f in (1.,.995)}


def write(p,v):p.write_text(json.dumps(clean(v),indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(job):
    c,arm,mode=job;d=OUT/f'{arm}-{mode}-{c["id"]:02d}';d.mkdir()
    kw=dict(barrier_frequency=3.,quality_factor=1.,early_id=True,tracking_only=False,adaptive=mode=='adaptive',mpc=mode!='lqr')
    if arm!='reference':kw.update(ARMS[arm])
    r,rows=run_episode(c,'lqr' if mode=='lqr' else 'deterministic',grid=mode!='lqr',controller_factory=Reference if arm=='reference' else Controller,controller_kwargs=kw)
    raw=d/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(x),allow_nan=False)+'\n' for x in rows));r.update(arm=arm,mode=mode,raw_sha256=sha(raw));write(d/'summary.json',r);return r


def main():
    OUT.mkdir(parents=True,exist_ok=False);cc=cases();files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files};write(OUT/'plan.json',dict(cases=cc,arms=ARMS,sources=hashes,expected_records=576,policies_changed=False,scope='historical training-only calibration'))
    for p in files:d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    jobs=[(c,'reference','lqr') for c in cc]+[(c,a,m) for c in cc for a in ARMS for m in ('optimized','adaptive')];assert len(jobs)==576;results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for i,f in enumerate(as_completed([pool.submit(run,j) for j in jobs]),1):
            results.append(f.result())
            if i%32==0:print('PARETO CALIBRATION',i,'/576',flush=True)
    write(OUT/'summary.json',results);base={r['case']['id']:r for r in results if r['arm']=='reference'};scores=[]
    for arm in ARMS:
        rr=[r for r in results if r['arm']==arm];by_mode={}
        for mode in ('optimized','adaptive'):
            sub=[r for r in rr if r['mode']==mode]
            ratios={f:float(np.mean([r[f] for r in sub])/np.mean([r[f] for r in base.values()])) for f in ('rmse_m','heading_rms','rate_rms')};by_mode[mode]=ratios
        progress=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in rr);fails=sum(r['failed'] for r in rr)
        eligible=fails==0 and progress>=.99 and all(x['heading_rms']<=1.+1e-12 and x['rate_rms']<=1.+1e-12 for x in by_mode.values())
        scores.append(dict(arm=arm,eligible=bool(eligible),failures=fails,minimum_progress_ratio=progress,by_mode=by_mode,mean_rmse=float(np.mean([r['rmse_m'] for r in rr]))))
    eligible=[s for s in scores if s['eligible']];selected=min(eligible,key=lambda s:(s['mean_rmse'],s['arm'])) if eligible else None
    write(OUT/'selection.json',dict(scores=scores,selected=selected));print(json.dumps(dict(scores=scores,selected=selected)),flush=True)


if __name__=='__main__':main()
