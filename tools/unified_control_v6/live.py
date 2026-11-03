"""Nine fixed actual-worker diagnostics with explicit selected-controller provenance."""
from dataclasses import replace
from pathlib import Path
import argparse,json,sys,time
from integrations.unified_lans.physics import Config
from integrations.unified_lans.inference import sha
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v5 import live as instrumentation
from .campaign import selected

ROOT=Path(__file__).resolve().parents[2]
_CACHE={}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=['selected','equivalent_fast'],default='selected')
    parser.add_argument('--output')
    args=parser.parse_args()
    choice,base=selected()
    if args.backend=='equivalent_fast':
        assert choice['candidate'].startswith('v6'), 'equivalent backend applies to the v6 solver'
        from .fast_control import Controller as base
        equivalence=ROOT.parent/'cloud-setup/proposal-v6-fast-equivalence-tests.log'
        assert equivalence.exists() and '1 passed' in equivalence.read_text()
        closed_loop=ROOT/'results/proposal-completion-v6/backend-equivalence/audit.json'
        assert json.loads(closed_loop.read_text())['passed']
    out=Path(args.output) if args.output else ROOT/('results/proposal-completion-v6/live-functional-fast' if args.backend=='equivalent_fast' else 'results/proposal-completion-v6/live-functional')
    out.mkdir(exist_ok=False)
    cases=[(seed,scenario,network,fault) for seed in [42,43,44] for scenario,network,fault in
           [('following','nominal','none'),('curved','ego_blackout','none'),('merge','nominal','crash')]]
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'FUNCTIONAL_PROTOCOL.md',Path(__file__).parent/'FAST_PROTOCOL.md',
           *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
           *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py']
    protocol=dict(role='FUNCTIONAL_DIAGNOSTIC_NOT_FORMAL_PROMOTION',selected=choice,cases=cases,backend=args.backend,
        calibration_sha256=sha(ROOT/'results/proposal-completion-v6/calibration/selection.json'),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        bindings='v5.live Controller -> selected controller, Config -> selected horizon, warmup -> matching full matrix grid',
        inference_policy_hashes={s:sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip') for s in [42,43,44]})
    if args.backend=='equivalent_fast':
        protocol['equivalence_log_sha256']=sha(equivalence)
        protocol['closed_loop_equivalence_sha256']=sha(closed_loop)
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    class SharedController(base):
        def __init__(self,*args,**kwargs):
            args=list(args)
            if len(args)>2:args[2]=replace(args[2],horizon=choice['horizon'])
            super().__init__(*args,**kwargs)
    original=instrumentation.mpc.matrices
    def matrices(*key):
        if key not in _CACHE:_CACHE[key]=original(*key)
        return _CACHE[key]
    instrumentation.mpc.matrices=matrices
    def warmup():
        start=time.perf_counter()
        for s in [i/20 for i in range(14,27)]:
            gain_table(16.,s)
            for v in [i/2 for i in range(4,34)]:matrices(v,s,16.,.05,round(choice['horizon']/.05))
        return time.perf_counter()-start
    instrumentation.Controller=SharedController
    instrumentation.Config=lambda **kwargs:Config(**{**kwargs,'horizon':choice['horizon']})
    instrumentation.warmup=warmup
    results=[]
    for seed,scenario,network,fault in cases:
        directory=out/f'seed-{seed}-{scenario}'
        sys.argv=['selected-live','--policy',str(ROOT/f'results/python-campaign-v2/policies/seed-{seed}'),
                  '--scenario',scenario,'--network',network,'--fault',fault,'--output',str(directory)]
        instrumentation.main()
        result=json.loads((directory/'summary.json').read_text());result.update(seed=seed,scenario=scenario)
        results.append(result)
        print('FIXED FUNCTIONAL CHECK',len(results),'/',len(cases),flush=True)
    (out/'summary.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
