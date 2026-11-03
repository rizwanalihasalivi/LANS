"""Development-only replay of known failures; never opens held-out cases."""
from functools import partial
from dataclasses import replace
import json
import argparse
from pathlib import Path
import numpy as np
from integrations.unified_lans.inference import load_policy
from tools.unified_campaign import study
from .control import Controller


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='results/corridor-v4/known-regressions');parser.add_argument('--mpc',action='store_true');parser.add_argument('--horizon',type=float,default=.5)
    a=parser.parse_args();root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    selected=json.loads(Path('results/corridor-v4/calibration/selection.json').read_text())['selected'];assert selected is not None
    penalty=selected['penalty'];model=load_policy('results/python-campaign-v2/policies/seed-42');all_results=[]
    for stage in ['development','robustness']:
        old=json.loads(Path(f'results/python-improvement-v3/{stage}_summary.json').read_text())
        cases={r['case']['id']:r['case'] for r in old}
        for case in cases.values():
            for mode in ['lqr','optimized','hybrid']:
                def factory(*args,**kwargs):
                    args=list(args);args[2]=replace(args[2],horizon=a.horizon)
                    return Controller(*args,penalty=penalty,adaptive=mode=='hybrid',mpc=a.mpc and mode in ('optimized','hybrid'),**kwargs)
                study.Pipeline=factory
                result,rows=study.run_episode(case,'deterministic' if mode=='optimized' else mode,
                    model if mode=='hybrid' else None,grid=mode in ('optimized','hybrid'))
                result['mode']=mode;all_results.append(dict(**result,old_stage=stage))
        for mode in ['lqr','optimized','hybrid']:
            rr=[r for r in all_results if r['old_stage']==stage and r['mode']==mode]
            print(stage,mode,'failures',sum(r['failed'] for r in rr),'/',len(rr),
                  'rmse',float(np.mean([r['rmse_m'] for r in rr])),flush=True)
    (root/'summary.json').write_text(json.dumps(all_results,indent=2))


if __name__=='__main__':main()
