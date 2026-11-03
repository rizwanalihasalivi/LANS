"""Fixed paired actual-worker measurements, not a 30% tracking promotion shortcut."""
from pathlib import Path
import json,sys,time
from integrations.unified_lans.physics import Config
from integrations.unified_lans.inference import sha
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v5 import live as instrumentation
from .campaign import make_controller,ROOT

_CACHE={}


def main():
    root=ROOT/'results/causal-v7/live-functional';root.mkdir(exist_ok=False)
    selections={role:json.loads((ROOT/f'results/causal-v7/{directory}/protocol.json').read_text())['selected']
                for role,directory in [('tracking_winner','confirmation'),('conic_engineering','engineering')]}
    cases=[(role,seed,scenario,network,fault) for role in selections for seed in [42,43,44]
        for scenario,network,fault in [('following','nominal','none'),('curved','ego_blackout','none'),('merge','nominal','crash')]]
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',Path(__file__).parent/'ENGINEERING_PROTOCOL.md',
        *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
        *(ROOT/'tools/unified_control_v6').glob('*.py'),*(ROOT/'integrations/unified_lans').glob('*.py')]
    protocol=dict(role='FUNCTIONAL_COMPUTATION_COMPARISON_NOT_TRACKING_PROMOTION',selections=selections,cases=cases,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        models={s:sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip') for s in [42,43,44]},
        calibration_sha256=sha(ROOT/'results/causal-v7/calibration/selection.json'),
        note='Identical non-native fixtures, all outcomes; fixed role order. Finite shared-cloud timings, no WCET guarantee.')
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        target=root/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    original=instrumentation.mpc.matrices
    def cached(*key):
        if key not in _CACHE:_CACHE[key]=original(*key)
        return _CACHE[key]
    instrumentation.mpc.matrices=cached
    results=[]
    for role,seed,scenario,network,fault in cases:
        selected=selections[role];horizon=selected['horizon'];directory=root/role/f'seed-{seed}-{scenario}';directory.parent.mkdir(exist_ok=True)
        def factory(*args,**kwargs):return make_controller(*args,selection=selected,**kwargs)
        def warmup():
            start=time.perf_counter()
            for s in [i/20 for i in range(14,27)]:
                gain_table(16.,s)
                if selected['factor'] is None:
                    for v in [i/2 for i in range(4,34)]:cached(v,s,16.,.05,round(horizon/.05))
            return time.perf_counter()-start
        instrumentation.Controller=factory;instrumentation.Config=lambda **kwargs:Config(**{**kwargs,'horizon':horizon});instrumentation.warmup=warmup
        sys.argv=['causal-live','--policy',str(ROOT/f'results/python-campaign-v2/policies/seed-{seed}'),
            '--scenario',scenario,'--network',network,'--fault',fault,'--output',str(directory)]
        instrumentation.main()
        result=json.loads((directory/'summary.json').read_text());result.update(controller_role=role,seed=seed,scenario=scenario)
        results.append(result);print('FIXED ACTUAL-WORKER CHECK',len(results),'/',len(cases),flush=True)
    (root/'summary.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
