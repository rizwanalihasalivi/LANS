"""Supported launcher with explicit audit import repair and conditional stages."""
import argparse
from pathlib import Path
from tools.unified_campaign import campaign as base
from .verify import imports


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',type=int,choices=[2,3],default=3)
    p.add_argument('--output',required=True)
    p.add_argument('--training',default='results/python-campaign-v2')
    a=p.parse_args()
    if a.version==3:
        from .campaign import configure
        configure(a.training)
    imports();root=Path(a.output)
    if not root.exists():base.prepare(root)
    base.train(root);base.evaluate(root,'development');gate=base.report(root,'development')
    stress=base.robustness(root);reserved='NOT_RUN'
    if gate['passed'] and stress:
        base.evaluate(root,'reserved');reserved=base.report(root,'reserved')
    passed=gate['passed'] and stress and isinstance(reserved,dict) and reserved['passed']
    base.write(root/'PYTHON_PERFORMANCE_GATE.json',dict(passed=passed,development=gate,
        robustness=stress,reserved=reserved,wall_worker='NOT_RUN',webots='NOT_RUN'))
    print('Python performance gate:',passed,flush=True)
    if not passed:print('Reserved/native stages remain closed; all outcomes retained.',flush=True)


if __name__=='__main__':main()
