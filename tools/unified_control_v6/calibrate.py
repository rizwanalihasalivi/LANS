"""Three predeclared training-only solver/horizon candidates, no learned policy."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v5.control import Controller as V5
from .control import Controller as V6

ROOT = Path(__file__).resolve().parents[2]


def main():
    root = ROOT / 'results/proposal-completion-v6/calibration'
    root.mkdir(parents=True, exist_ok=False)
    candidates = [('v5-h1', V5, 1.), ('v6-h1', V6, 1.), ('v6-h2', V6, 2.)]
    sources = [*Path(__file__).parent.glob('*.py'), Path(__file__).parent/'PROTOCOL.md',
               *(ROOT/'tools/unified_control_v4').glob('*.py'),
               *(ROOT/'tools/unified_control_v5').glob('*.py'),
               *(ROOT/'integrations/unified_lans').glob('*.py'), ROOT/'tools/unified_campaign/study.py']
    protocol = dict(candidates=[n for n, _, _ in candidates], cases=cases(), seconds=6.,
                    penalty=16., modes=['optimized', 'adaptive'], new_training_steps=0,
                    selector='zero failures; progress>=99% max stable; heading/rate<=110% LQR; minimum balanced cost',
                    sources={str(p.relative_to(ROOT)):sha(p) for p in sources})
    (root/'protocol.json').write_text(json.dumps(protocol, indent=2))
    for p in sources:
        dest=root/'source'/p.relative_to(ROOT); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(p.read_bytes())
    results=[]
    for name, cls, horizon in [('lqr', V5, 1.), *candidates]:
        for mode in ['lqr'] if name=='lqr' else protocol['modes']:
            def factory(*args, **kwargs):
                args=list(args);args[2]=replace(args[2],horizon=horizon)
                return cls(*args,penalty=16.,adaptive=mode=='adaptive',mpc=mode!='lqr',**kwargs)
            study.Pipeline=factory
            for case in protocol['cases']:
                record, rows=study.run_episode(case,'lqr' if mode=='lqr' else 'deterministic',grid=mode!='lqr')
                raw=root/f'{name}-{mode}-{case["id"]:02d}.jsonl'
                raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
                results.append(dict(**{**record,'mode':mode},candidate=name,raw_sha256=sha(raw)))
            rr=[r for r in results if r['candidate']==name and r['mode']==mode]
            print(name,mode,'failures',sum(r['failed'] for r in rr),'rmse',np.mean([r['rmse_m'] for r in rr]),flush=True)
    baseline=[r for r in results if r['candidate']=='lqr'];scores=[]
    for name, _, horizon in candidates:
        rr=[r for r in results if r['candidate']==name]
        scores.append(dict(candidate=name,horizon=horizon,failures=sum(r['failed'] for r in rr),
            progress=float(np.mean([r['progress_m'] for r in rr])),
            balanced=float(np.mean([r['rmse_m']+.1*r['heading_rms']+.01*r['rate_rms'] for r in rr])),
            heading_ratio=float(np.mean([r['heading_rms'] for r in rr])/np.mean([r['heading_rms'] for r in baseline])),
            rate_ratio=float(np.mean([r['rate_rms'] for r in rr])/np.mean([r['rate_rms'] for r in baseline]))))
    eligible=[s for s in scores if s['failures']==0]
    maximum=max((s['progress'] for s in eligible),default=0.)
    eligible=[s for s in eligible if s['progress']>=.99*maximum and s['heading_ratio']<=1.10 and s['rate_ratio']<=1.10]
    selected=min(eligible,key=lambda s:(s['balanced'],s['candidate'])) if eligible else None
    (root/'summary.json').write_text(json.dumps(clean(results),indent=2))
    (root/'selection.json').write_text(json.dumps(dict(selected=selected,scores=scores),indent=2))
    print('SELECTION',selected,flush=True)


if __name__=='__main__':main()
