"""Training-only common horizon calibration; no learned-seed or test-case selection."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from .calibrate import cases
from .control import Controller


def main():
    root=Path('results/corridor-v4/lookahead-calibration');root.mkdir(parents=True,exist_ok=False)
    penalty=json.loads(Path('results/corridor-v4/calibration/selection.json').read_text())['selected']['penalty']
    protocol=dict(horizons=[.25,.5,1.],penalty=penalty,cases=cases(),modes=['optimized','adaptive'],seconds=6.,
        selector='zero failures, >=99% of maximum stable mean progress, minimum balanced cost across both modes',
        objective='rmse + 0.1*heading_rms + 0.01*rate_rms',no_learned_policy_used=True)
    files=[*Path(__file__).parent.glob('*.py'),Path('integrations/unified_lans/controller.py')]
    protocol['sources']={str(p):sha(p) for p in files};(root/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        path=p if not p.is_absolute() else p.relative_to(Path.cwd())
        target=root/'source'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    results=[]
    for horizon in protocol['horizons']:
        for mode in protocol['modes']:
            def factory(*args,**kwargs):
                args=list(args);args[2]=replace(args[2],horizon=horizon)
                return Controller(*args,penalty=penalty,adaptive=mode=='adaptive',**kwargs)
            study.Pipeline=factory
            for case in protocol['cases']:
                result,rows=study.run_episode(case,'deterministic',grid=True,seconds=6.)
                result.update(mode=mode,horizon=horizon)
                raw=root/f'H-{horizon:g}-{mode}-case-{case["id"]:02d}.jsonl'
                raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows));result['raw_sha256']=sha(raw)
                results.append(result)
            rr=[r for r in results if r['horizon']==horizon and r['mode']==mode]
            print('HORIZON',horizon,mode,'failures',sum(r['failed'] for r in rr),'rmse',np.mean([r['rmse_m'] for r in rr]),flush=True)
    scores=[]
    for h in protocol['horizons']:
        rr=[r for r in results if r['horizon']==h]
        scores.append(dict(horizon=h,failures=sum(r['failed'] for r in rr),progress=float(np.mean([r['progress_m'] for r in rr])),
            cost=float(np.mean([r['rmse_m']+.1*r['heading_rms']+.01*r['rate_rms'] for r in rr]))))
    eligible=[r for r in scores if r['failures']==0]
    if eligible:
        progress=max(r['progress'] for r in eligible);eligible=[r for r in eligible if r['progress']>=.99*progress]
    selected=min(eligible,key=lambda r:(r['cost'],r['horizon'])) if eligible else None
    (root/'summary.json').write_text(json.dumps(clean(results),indent=2));(root/'selection.json').write_text(json.dumps(dict(selected=selected,scores=scores),indent=2))
    print('SELECTED HORIZON',selected,flush=True)


if __name__=='__main__':main()
