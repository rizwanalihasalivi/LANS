"""Finite geometric-law calibration on the common training-only fixtures."""
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor,as_completed
import multiprocessing as mp,json,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v8.control import Controller as LQR
from .baselines import Controller,PARAMETERS

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/publication-v9/baseline-calibration'


def worker(job):
    method,parameter,case=job;key=f'{method}-{parameter:g}-{case["id"]:02d}'
    raw=OUT/(key+'.jsonl');meta=OUT/(key+'.json')
    assert not raw.exists() and not meta.exists()
    def factory(*args,**kwargs):
        args=list(args);args[2]=replace(args[2],horizon=2.)
        if method=='lqr':return LQR(*args,penalty=16.,adaptive=False,mpc=False,**kwargs)
        return Controller(*args,method=method,parameter=parameter,**kwargs)
    study.Pipeline=factory;r,rows=study.run_episode(case,'lqr',seconds=6.)
    raw.write_text(''.join(json.dumps(clean(row),allow_nan=False)+'\n' for row in rows))
    r.update(method=method,parameter=parameter,raw_sha256=sha(raw),protocol_sha256=sha(OUT/'protocol.json'))
    meta.write_text(json.dumps(r,indent=2));return r


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),Path(__file__).with_name('baselines.py'),Path(__file__).with_name('BASELINE_PROVENANCE.md'),
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py']
    for v in range(4,9):paths.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    protocol=dict(cases=cases(),candidates=PARAMETERS,total=448,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in paths},
        selection='Zero failures, every progress>=99% matched LQR, then minimum mean RMSE+.1heading+.01rate; retain diagnostic fallback explicitly if no method candidate qualifies')
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in paths:
        dest=OUT/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    jobs=[(method,value,case) for method,values in dict(lqr=[16.],**PARAMETERS).items() for value in values for case in cases()]
    records=[]
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn')) as pool:
        for i,f in enumerate(as_completed([pool.submit(worker,job) for job in jobs]),1):
            records.append(f.result())
            if i%32==0:print('GEOMETRIC CALIBRATION',i,'/448',flush=True)
    records.sort(key=lambda r:(r['method'],r['parameter'],r['case']['id']))
    base={r['case']['id']:r for r in records if r['method']=='lqr'};scores=[];selected={}
    for method,parameters in PARAMETERS.items():
        for parameter in parameters:
            rr=[r for r in records if r['method']==method and r['parameter']==parameter]
            scores.append(dict(method=method,parameter=parameter,failures=sum(r['failed'] for r in rr),
                minimum_progress_ratio=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in rr),
                mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),
                score=float(np.mean([r['rmse_m']+.1*r['heading_rms']+.01*r['rate_rms'] for r in rr]))))
        eligible=[s for s in scores if s['method']==method and s['failures']==0 and s['minimum_progress_ratio']>=.99]
        fallback=not eligible
        if fallback:eligible=[s for s in scores if s['method']==method]
        selected[method]=dict(**min(eligible,key=lambda s:(s['failures'],s['score'],s['parameter'])),diagnostic_fallback=fallback)
    (OUT/'summary.json').write_text(json.dumps(records,indent=2))
    (OUT/'selection.json').write_text(json.dumps(dict(selected=selected,scores=scores),indent=2))
    print(json.dumps(selected),flush=True)


if __name__=='__main__':main()
