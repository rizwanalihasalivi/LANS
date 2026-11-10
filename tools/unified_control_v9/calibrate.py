"""Three asynchronous candidates, synchronous reference and matched LQR."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
from pathlib import Path
import json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v8.control import Controller as Legacy
from .control import Controller

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/publication-v9/calibration'
CANDIDATES=[dict(name='v8-synchronous',sync=True,quality_factor=1.1,guard_factor=1.1,nominal_feedback=False),
    dict(name='async-original',sync=False,quality_factor=1.1,guard_factor=1.1,nominal_feedback=False),
    dict(name='async-strict',sync=False,quality_factor=1.,guard_factor=1.,nominal_feedback=False),
    dict(name='async-strict-nominal-feedback',sync=False,quality_factor=1.,guard_factor=1.,nominal_feedback=True)]


def factory(candidate,*args,role='adaptive',**kwargs):
    args=list(args)
    if len(args)>2:args[2]=replace(args[2],horizon=2.)
    elif kwargs.get('cfg') is not None:kwargs['cfg']=replace(kwargs['cfg'],horizon=2.)
    cls=Legacy if candidate['sync'] else Controller
    kwargs.update(quality_factor=candidate['quality_factor'],early_id=True,tracking_only=False)
    if not candidate['sync']:kwargs.update(guard_factor=candidate['guard_factor'],nominal_feedback=candidate['nominal_feedback'],planner_backend='logical')
    kwargs.pop('penalty',None)
    return cls(*args,penalty=16.,adaptive=role in ('adaptive','hybrid'),mpc=role in ('optimized','adaptive','hybrid'),**kwargs)


def prepare():
    root=OUTPUT;root.mkdir(parents=True,exist_ok=False)
    files=[*(Path(__file__).parent/name for name in ['calibrate.py','control.py','runtime.py','PROTOCOL.md']),
           *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
           *(ROOT/'tools/unified_control_v6').glob('*.py'),*(ROOT/'tools/unified_control_v7').glob('*.py'),*(ROOT/'tools/unified_control_v8').glob('*.py'),
           *(ROOT/'integrations/unified_lans').glob('*.py'),
           ROOT/'tools/unified_campaign/study.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    protocol=dict(candidates=CANDIDATES,cases=cases(),horizons=[2.],modes=['optimized','adaptive'],
        total_episodes=576,seeds_selected=False,new_training_steps=0,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        selector='Only async candidates: zero failures and every progress>=99%; prefer heading/rate<=100% in both modes, otherwise explicit <=110% diagnostic fallback; minimum mean RMSE, name tie-break')
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        target=root/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    return protocol


def worker(job):
    candidate,mode,case=job;root=OUTPUT;key=f'{candidate["name"]}-{mode}-{case["id"]:02d}'
    raw=root/(key+'.jsonl');meta=root/(key+'.json')
    if meta.exists():
        record=json.loads(meta.read_text());assert sha(raw)==record['raw_sha256'];return record
    assert not raw.exists(),('Preserve interrupted evidence',raw)
    study.Pipeline=lambda *args,**kwargs:factory(candidate,*args,role=mode,**kwargs)
    record,rows=study.run_episode(case,'lqr' if mode=='lqr' else 'deterministic',grid=mode!='lqr')
    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(mode=mode,candidate=candidate['name'],horizon=2.,raw_sha256=sha(raw),protocol_sha256=sha(root/'protocol.json'))
    meta.write_text(json.dumps(clean(record),indent=2));return record


def main():
    protocol=prepare() if not OUTPUT.exists() else json.loads((OUTPUT/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    baselines=[dict(name='lqr-h2',sync=True,quality_factor=1.1,guard_factor=1.1,nominal_feedback=False)]
    jobs=[(candidate,mode,case) for candidate in baselines+CANDIDATES for mode in (['lqr'] if candidate['name'].startswith('lqr') else protocol['modes']) for case in protocol['cases']]
    assert len(jobs)==576;results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for future in as_completed([pool.submit(worker,j) for j in jobs]):
            results.append(future.result())
            if len(results)%16==0:print('CALIBRATION EPISODES',len(results),'/576',flush=True)
    results.sort(key=lambda r:(r["candidate"],r["mode"],r["case"]["id"]))
    scores=[]
    for candidate in CANDIDATES:
        rr=[r for r in results if r['candidate']==candidate['name']]
        base={r['case']['id']:r for r in results if r['candidate']=='lqr-h2'}
        by_mode={}
        for mode in protocol['modes']:
            mm=[r for r in rr if r['mode']==mode]
            by_mode[mode]=dict(heading_ratio=float(np.mean([r['heading_rms'] for r in mm])/np.mean([r['heading_rms'] for r in base.values()])),
                rate_ratio=float(np.mean([r['rate_rms'] for r in mm])/np.mean([r['rate_rms'] for r in base.values()])))
        heading=max(m['heading_ratio'] for m in by_mode.values());rate=max(m['rate_ratio'] for m in by_mode.values())
        progress=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in rr)
        scores.append(dict(**candidate,failures=sum(r['failed'] for r in rr),heading_ratio=heading,rate_ratio=rate,
            minimum_progress_ratio=progress,mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),by_mode=by_mode))
    stable=[s for s in scores if not s['sync'] and s['failures']==0 and s['minimum_progress_ratio']>=.99-1e-12]
    strict=[s for s in stable if s['heading_ratio']<=1.+1e-12 and s['rate_ratio']<=1.+1e-12]
    old=[s for s in stable if s['heading_ratio']<=1.10+1e-12 and s['rate_ratio']<=1.10+1e-12]
    eligible=strict or old
    selected=min(eligible,key=lambda s:(s['mean_rmse_m'],s['name'])) if eligible else None
    (OUTPUT/'summary.json').write_text(json.dumps(clean(results),indent=2))
    (OUTPUT/'selection.json').write_text(json.dumps(dict(selected=selected,scores=scores,no_quality_regression_passed=bool(strict),diagnostic_fallback=bool(not strict and old)),indent=2))
    print('SELECTED',json.dumps(selected),flush=True)
    print('SCORES',json.dumps(scores),flush=True)


if __name__=='__main__':main()
