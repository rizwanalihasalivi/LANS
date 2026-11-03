"""Verification-only missing-import repair for preserved v2/v3 campaign records."""
import argparse
import math
from pathlib import Path
from tools.unified_campaign import campaign as base
from integrations.unified_lans.physics import Command
from integrations.unified_lans.inference import sha


def imports():
    base.Command=Command
    base.math=math


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--version',type=int,choices=[2,3],required=True)
    p.add_argument('--training',default='results/python-campaign-v2');a=p.parse_args()
    if a.version==3:
        from .campaign import configure
        configure(a.training)
    imports();root=base.check(Path(a.output))
    base.write(root/'VERIFIER_IMPORT_REPAIR.json',dict(original_failures=['missing Command import','missing math import'],
        repair='Bind existing Command and standard-library math in auditor namespace only',
        repair_source_sha256=sha(__file__),raw_records_changed=False,raw_episodes_rerun=False,
        formulas_tolerances_thresholds_changed=False))
    gate=base.report(root,'development');stress=base.robustness(root)
    reserved='NOT_RUN'
    if gate['passed'] and stress:
        base.evaluate(root,'reserved');reserved=base.report(root,'reserved')
    passed=gate['passed'] and stress and isinstance(reserved,dict) and reserved['passed']
    base.write(root/'PYTHON_PERFORMANCE_GATE.json',dict(passed=passed,development=gate,robustness=stress,
        reserved=reserved,wall_worker='NOT_RUN',webots='NOT_RUN'))
    print('PERFORMANCE GATE',passed,'; actual worker/native stages remain conditional.',flush=True)


if __name__=='__main__':main()
