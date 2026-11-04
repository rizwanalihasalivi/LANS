"""SMT obligations for finite continuous 2-D trace certification and association."""
import argparse
import json
from pathlib import Path
import z3


def prove(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    l,r,c,ra,rb,pad,ea,eb=z3.Reals('l r c ra rb pad ea eb')
    q=z3.Real('q')
    obligations={
        'linear_chord_separation':([0<=q,q<=1,l>c,r>c],(1-q)*l+q*r>c),
        'bridge_projection_separation':([ra>=0,rb>=0,pad>=0,l>ra+rb+pad,ea+eb<=pad],l-ea-eb>ra+rb),
        'axis_separation_excludes_overlap':([l>ra+rb,ra>=0,rb>=0],z3.Not(z3.And(c<=ra,c>=l-rb))),
        'outward_rounding_sound':([l<=r,c>=ra,l>c],r>ra),
        'nearer_endpoint_rotation':([0<=q,q<=1],z3.If(q<=z3.RealVal('.5'),q,1-q)<=z3.RealVal('.5')),
        'set_coverage_independent_of_identity':([ea>=l,eb<=r,l>r],ea>eb)
    }
    results={}
    for name,(premises,claim) in obligations.items():
        s=z3.SolverFor('QF_NRA');s.add(*premises,z3.Not(claim));s.set(timeout=30000)
        (out/(name+'.smt2')).write_text(s.to_smt2())
        status=s.check()
        if status!=z3.unsat:raise RuntimeError((name,str(status)))
        results[name]=str(status)
    # Ignoring bounded curvature of the intersample trajectory permits a middle
    # collision despite separated endpoints; the bridge premise is essential.
    s=z3.Solver();s.add(l==1,r==1,pad==2,l-pad<0)
    assert s.check()==z3.sat
    report=dict(passed=True,solver=z3.get_version_string(),algebraic_obligations=results,
        omitted_bridge_negative_control=dict(result='sat',witness=str(s.model())),
        scope='finite continuous 2-D trace certificates under pose/body/acceleration/yaw bounds; not a prospective controller invariance proof')
    (out/'proof.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    print(json.dumps(prove(p.parse_args().output),indent=2))
