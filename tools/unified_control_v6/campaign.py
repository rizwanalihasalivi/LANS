"""Frozen confirmation of the finite training-only selected shared planner."""
import json
from dataclasses import replace
from pathlib import Path
import numpy as np
from integrations.unified_lans.inference import sha
from tools.unified_control_v4 import campaign as base
from tools.unified_control_v5.control import Controller as V5
from .control import Controller as V6


def selected():
    path=base.ROOT/'results/proposal-completion-v6/calibration/selection.json'
    choice=json.loads(path.read_text())['selected']
    assert choice is not None, 'No training-only candidate met the fixed selector'
    return choice, V5 if choice['candidate'].startswith('v5') else V6


def configure():
    choice,controller=selected()
    class SharedController(controller):
        def __init__(self,*args,**kwargs):
            args=list(args)
            if len(args)>2:args[2]=replace(args[2],horizon=choice['horizon'])
            elif kwargs.get('cfg') is not None:kwargs['cfg']=replace(kwargs['cfg'],horizon=choice['horizon'])
            super().__init__(*args,**kwargs)
    base.RUN=base.ROOT/'results/proposal-completion-v6/confirmation'
    original_prepare=base.prepare; original_check=base.check; old_cases=base.cases
    def prepare(root):
        p=original_prepare(root);p['version']=6;p['config']['horizon']=choice['horizon']
        p['selected_shared_planner']=choice
        p['solver_calibration_sha256']=sha(base.ROOT/'results/proposal-completion-v6/calibration/selection.json')
        p['changes'].append('finite training-only selection of shared nonlinear solver and horizon')
        p['development']=dict(namespace=15410000,phase=11.,amplitude=1.2)
        p['reserved']=dict(namespace=18410000,phase=23.,amplitude=1.3)
        files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',
               *(base.ROOT/'tools/unified_control_v5').glob('*.py')]
        for path in files:
            name=str(path.relative_to(base.ROOT));p['source_hashes'][name]=sha(path)
            target=root/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
        base.write(root/'protocol.json',p);return p
    def check(root):
        p=original_check(root);assert p['version']==6
        assert p['solver_calibration_sha256']==sha(base.ROOT/'results/proposal-completion-v6/calibration/selection.json')
        return p
    def cases(stage):
        if stage.startswith('regression'):return old_cases(stage)
        rr=old_cases(stage)
        if stage=='stress':
            for c in rr:c.update(stage='v6_stress',phase=11.,amplitude=1.2,network_seed=c['network_seed']+11000000)
            return rr
        reserved=stage=='reserved';rng=np.random.default_rng(18410000 if reserved else 15410000)
        for c in rr:
            c.update(stage='v6_'+stage,lateral=float(rng.uniform(.15,.45))*c['mirror'],heading=float(rng.uniform(-.015,.015)),
                     phase=23. if reserved else 11.,amplitude=1.3 if reserved else 1.2,
                     network_seed=(18510000 if reserved else 15510000)+c['id'])
        return rr
    base.prepare=prepare;base.check=check;base.cases=cases;base.Controller=SharedController


if __name__=='__main__':
    configure();base.main()
