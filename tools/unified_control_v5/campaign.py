"""Separately frozen nonlinear-plan repair; numeric promotion rules are unchanged."""
import argparse,json
from dataclasses import replace
from pathlib import Path
import numpy as np
from tools.unified_control_v4 import campaign as base
from tools.unified_campaign import study
from integrations.unified_lans.inference import sha
from .control import Controller


def configure():
    base.RUN=base.ROOT/'results/corridor-v5/confirmation-campaign'
    original_prepare=base.prepare;original_check=base.check;old_cases=base.cases
    def prepare(root):
        p=original_prepare(root);p['version']=5
        p['changes'].append('nonlinear planned braking refinement shared by optimized/adaptive/hybrid')
        p['refinement']=dict(sweeps=[.01,.0025],blocks=4,signs=[-1,1],extra_training_steps=0)
        p['development']=dict(namespace=5410000,phase=9.,amplitude=1.15)
        p['reserved']=dict(namespace=8410000,phase=21.,amplitude=1.25)
        for path in Path(__file__).parent.glob('*.py'):
            name=str(path.relative_to(base.ROOT));p['source_hashes'][name]=sha(path)
            target=root/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
        base.write(root/'protocol.json',p);return p
    def check(root):
        p=original_check(root);assert p['version']==5;return p
    def cases(stage):
        if stage.startswith('regression'):return old_cases(stage)
        rr=old_cases(stage)
        if stage=='stress':
            for c in rr:c['phase']=9.;c['network_seed']+=2000000
            return rr
        reserved=stage=='reserved';rng=np.random.default_rng(8410000 if reserved else 5410000)
        for c in rr:
            c.update(stage='v5_'+stage,lateral=float(rng.uniform(.15,.45))*c['mirror'],heading=float(rng.uniform(-.015,.015)),
                phase=21. if reserved else 9.,network_seed=(8510000 if reserved else 5510000)+c['id'])
        return rr
    base.prepare=prepare;base.check=check;base.cases=cases;base.Controller=Controller


if __name__=='__main__':
    configure();base.main()
