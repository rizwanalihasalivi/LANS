"""Deterministic exact boundary checks and deliberate contract violations."""
import argparse
from fractions import Fraction as F
import itertools
import json
from pathlib import Path
from .shield import Contract,SafetyShield,ContractViolation
from .audit import flow,gap_minimum


def run():
    count=0
    for v,b,h,delta,slack,nominal in itertools.product(
            map(F,('0','.01','8','16','30')),map(F,('3','5.5','8')),
            map(F,('.01','.05','.1')),map(F,('0','.25','1')),
            map(F,('0','.000001','1','20')),map(F,('-100','0','2.5','100'))):
        cfg=Contract(brake=b,horizon=h,uncertainty=delta)
        B=cfg.margin+v*v/(2*b)+slack
        shield=SafetyShield(0,v,contract=cfg)
        assert shield.observe('front','radar',0,0,0,B,F('.2'))
        command,cert=shield.choose(nominal)
        xn,vn=flow(F(0),v,command+delta,h)
        assert vn*vn<=2*b*(B-xn-cfg.margin)
        assert gap_minimum(F(0),v,command+delta,B,F(0),F(0),h)>=cfg.margin
        assert F(cert['guard_slack_scaled'])>=0
        count+=1
    bad=SafetyShield(0,16)
    bad.observe('front','radar',0,0,0,1,F('.2'))
    try:bad.choose(0)
    except ContractViolation:rejected=True
    else:raise AssertionError('unsafe admission was accepted')
    collision=gap_minimum(F(0),F(16),F('-5.5'),F(1),F(0),F(0),F(4))
    assert collision<0
    cfg=Contract();v=F(16);B=cfg.margin+v*v/(2*cfg.brake)
    weak_brake=gap_minimum(F(0),v,F(-2),B,F(0),F(0),F(8))
    assert weak_brake<0
    return dict(passed=True,boundary_cases=count,unsafe_admission_rejected=rejected,
        excluded_unsafe_cutin=dict(contract_valid=False,minimum_gap_m=float(collision)),
        excluded_weak_brake=dict(contract_valid=False,minimum_gap_m=float(weak_brake)),
        note='Negative-gap diagnostics are deliberate OUTSIDE-CONTRACT counterexamples, not valid-cohort passes.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    path=Path(a.output)
    if path.exists():raise SystemExit('refusing to overwrite boundary evidence')
    result=run();path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
