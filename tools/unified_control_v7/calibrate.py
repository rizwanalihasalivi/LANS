"""Four fixed shared-controller candidates, with matched LQR for both horizons."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
from pathlib import Path
import json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v6.control import Controller as Legacy
from .control import Controller

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/causal-v7/calibration'
CANDIDATES=[dict(name='v6-h2',horizon=2.,factor=None),dict(name='conic-h1-q104',horizon=1.,factor=1.04),
            dict(name='conic-h1-q110',horizon=1.,factor=1.10),dict(name='conic-h2-q110',horizon=2.,factor=1.10)]


def prepare():
    root=OUTPUT;root.mkdir(parents=True,exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',
           *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
           *(ROOT/'tools/unified_control_v6').glob('*.py'),*(ROOT/'integrations/unified_lans').glob('*.py'),
           ROOT/'tools/unified_campaign/study.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    protocol=dict(candidates=CANDIDATES,cases=cases(),horizons=[1.,2.],modes=['optimized','adaptive'],
        total_episodes=640,seeds_selected=False,new_training_steps=0,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        selector='zero failures; original actual mean heading/rate<=110% matched LQR; all cell progress>=99%; minimum mean RMSE; name tie-break')
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
    cls=Legacy if candidate['factor'] is None else Controller
    def factory(*args,**kwargs):
        args=list(args);args[2]=replace(args[2],horizon=candidate['horizon'])
        if candidate['factor'] is not None:kwargs['quality_factor']=candidate['factor']
        return cls(*args,penalty=16.,adaptive=mode=='adaptive',mpc=mode!='lqr',**kwargs)
    study.Pipeline=factory
    record,rows=study.run_episode(case,'lqr' if mode=='lqr' else 'deterministic',grid=mode!='lqr')
    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(mode=mode,candidate=candidate['name'],horizon=candidate['horizon'],raw_sha256=sha(raw),protocol_sha256=sha(root/'protocol.json'))
    meta.write_text(json.dumps(clean(record),indent=2));return record


def main():
    protocol=prepare() if not OUTPUT.exists() else json.loads((OUTPUT/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    baselines=[dict(name=f'lqr-h{h:g}',horizon=h,factor=None) for h in protocol['horizons']]
    jobs=[(candidate,mode,case) for candidate in baselines+CANDIDATES for mode in (['lqr'] if candidate['name'].startswith('lqr') else protocol['modes']) for case in protocol['cases']]
    assert len(jobs)==640;results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for future in as_completed([pool.submit(worker,j) for j in jobs]):
            results.append(future.result())
            if len(results)%16==0:print('CALIBRATION EPISODES',len(results),'/640',flush=True)
    scores=[]
    for candidate in CANDIDATES:
        rr=[r for r in results if r['candidate']==candidate['name']]
        base={r['case']['id']:r for r in results if r['candidate']==f'lqr-h{candidate["horizon"]:g}'}
        by_mode={}
        for mode in protocol['modes']:
            mm=[r for r in rr if r['mode']==mode]
            by_mode[mode]=dict(heading_ratio=float(np.mean([r['heading_rms'] for r in mm])/np.mean([r['heading_rms'] for r in base.values()])),
                rate_ratio=float(np.mean([r['rate_rms'] for r in mm])/np.mean([r['rate_rms'] for r in base.values()])))
        heading=max(m['heading_ratio'] for m in by_mode.values());rate=max(m['rate_ratio'] for m in by_mode.values())
        progress=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in rr)
        scores.append(dict(**candidate,failures=sum(r['failed'] for r in rr),heading_ratio=heading,rate_ratio=rate,
            minimum_progress_ratio=progress,mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),by_mode=by_mode))
    eligible=[s for s in scores if s['failures']==0 and s['heading_ratio']<=1.10+1e-12 and s['rate_ratio']<=1.10+1e-12 and s['minimum_progress_ratio']>=.99-1e-12]
    selected=min(eligible,key=lambda s:(s['mean_rmse_m'],s['name'])) if eligible else None
    (OUTPUT/'summary.json').write_text(json.dumps(clean(results),indent=2))
    (OUTPUT/'selection.json').write_text(json.dumps(dict(selected=selected,scores=scores),indent=2))
    print('SELECTED',json.dumps(selected),flush=True)
    print('SCORES',json.dumps(scores),flush=True)


if __name__=='__main__':main()
