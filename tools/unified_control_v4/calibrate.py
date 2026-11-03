"""Finite shared-baseline calibration on training-only cases, before confirmation."""
from dataclasses import asdict
from functools import partial
import itertools,json
from pathlib import Path
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from integrations.unified_lans.physics import Config
from tools.unified_campaign import study
from .control import Controller


def cases():
    rng=np.random.default_rng(2310041);out=[]
    grid=itertools.product(['following','merge','crossing','curved'],[1,-1],[8.,16.],[.8,1.2],[0.,.1])
    for index,(scenario,mirror,speed,stiffness,delay) in enumerate(grid):
        out.append(dict(id=index,stage='calibration_only',scenario=scenario,mirror=mirror,speed=speed,
            stiffness=stiffness,delay=delay,lateral=float(rng.uniform(.15,.45))*mirror,
            heading=float(rng.uniform(-.015,.015)),phase=1.,amplitude=.9,network='nominal',network_seed=2311000+index))
    return out


def main():
    root=Path('results/corridor-v4/calibration');root.mkdir(parents=True,exist_ok=False)
    protocol=dict(penalties=[1.,4.,16.,64.],cases=cases(),seconds=6.,config=asdict(Config()),
        selector='zero failures, then >=99% of maximum stable mean progress, then balanced tracking/heading/rate cost',
        objective='rmse + 0.1*heading_rms + 0.01*rate_rms',no_confirmation_data_read=True)
    sources=[*Path(__file__).parent.glob('*.py'),Path('integrations/unified_lans/controller.py'),Path('integrations/unified_lans/physics.py')]
    protocol['sources']={str(p):sha(p) for p in sources}
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2));summaries=[]
    for penalty in protocol['penalties']:
        study.Pipeline=partial(Controller,penalty=penalty,adaptive=False,corridor=True,backup=True)
        for case in protocol['cases']:
            meta,rows=study.run_episode(case,'lqr',seconds=6.)
            raw=root/f'R-{penalty:g}-case-{case["id"]:02d}.jsonl'
            raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
            summaries.append(dict(**meta,penalty=penalty,raw_sha256=sha(raw)))
        selected=[r for r in summaries if r['penalty']==penalty]
        print('CALIBRATION',penalty,'failures',sum(r['failed'] for r in selected),'/',len(selected),flush=True)
    scores=[]
    for penalty in protocol['penalties']:
        rr=[r for r in summaries if r['penalty']==penalty]
        scores.append(dict(penalty=penalty,failures=sum(r['failed'] for r in rr),progress=float(np.mean([r['progress_m'] for r in rr])),
            cost=float(np.mean([r['rmse_m']+.1*r['heading_rms']+.01*r['rate_rms'] for r in rr]))))
    eligible=[s for s in scores if s['failures']==0]
    if eligible:
        maximum=max(s['progress'] for s in eligible);eligible=[s for s in eligible if s['progress']>=.99*maximum]
    selected=min(eligible,key=lambda s:(s['cost'],s['penalty'])) if eligible else None
    (root/'summary.json').write_text(json.dumps(clean(summaries),indent=2))
    (root/'selection.json').write_text(json.dumps(dict(selected=selected,scores=scores),indent=2))
    print('SELECTED',selected,flush=True)


if __name__=='__main__':main()
