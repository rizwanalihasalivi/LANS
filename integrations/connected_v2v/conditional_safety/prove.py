"""Export/check real-arithmetic obligations and SAT negative controls with Z3.

UNSAT is a trusted-SMT result, not a proof-assistant-kernel certificate or a
formal verification of Python/NumPy/Webots. See THEOREM.md for the flow lemma.
"""
import argparse
import hashlib
import json
from pathlib import Path
import z3


def obligations():
    R = z3.RealVal
    b,v,h,m,X,B,a,s,w,Xn,Vn,Bn,d,P,Y = z3.Reals('b v h m X B a s w Xn Vn Bn d P Y')
    positive = [b>0, v>=0, h>0, m>0]
    inv = v*v <= 2*b*(B-X-m)
    guard = 2*b*s+w*w <= 2*b*(B-X-m)
    cases = {}
    cases['brake_moving_identity'] = (positive+[v>=b*h, s==v*h-b*h*h/2, w==v-b*h],
        z3.And(s>=0,w>=0,2*b*s+w*w==v*v))
    cases['brake_stopped_identity'] = (positive+[v<b*h,2*b*s==v*v,w==0],
        z3.And(s>=0,w>=0,2*b*s+w*w==v*v))
    cases['emergency_feasible_moving'] = (positive+[inv,v>=b*h,s==v*h-b*h*h/2,w==v-b*h],guard)
    cases['emergency_feasible_stopped'] = (positive+[inv,v<b*h,2*b*s==v*v,w==0],guard)
    cases['guard_preserves_invariant'] = (positive+[s>=0,w>=0,guard,Xn<=X+s,0<=Vn,Vn<=w,Bn>=B],
        Vn*Vn<=2*b*(Bn-Xn-m))
    cases['continuous_gap_from_envelope'] = (positive+[s>=0,w>=0,guard,0<=d,d<=s,P>=B,Y<=X+d],P-Y>=m)
    # Intersecting with new valid upper bounds only reduces stopping demand.
    cases['ego_interval_refinement'] = (positive+[inv,Xn<=X,0<=Vn,Vn<=v],Vn*Vn<=2*b*(B-Xn-m))
    old, new, pos_old, pos_now = z3.Reals('old new pos_old pos_now')
    cases['stale_spatial_bound_retention'] = ([old<=pos_old,pos_old<=pos_now],old<=pos_now)
    cases['max_valid_spatial_bounds'] = ([old<=pos_now,new<=pos_now],z3.If(old>new,old,new)<=pos_now)
    measured,error = z3.Reals('measured error')
    cases['sensor_lower_containment'] = ([error>=0,measured-pos_old<=error],measured-error<=pos_old)
    cases['monotone_ego_flow_moving'] = (positive+[a>=-b,v+a*h>=0,s==v*h+a*h*h/2,w==v+a*h],z3.And(s>=0,w>=0))
    cases['monotone_ego_flow_stopped'] = (positive+[a<0,v+a*h<0,2*(-a)*s==v*v,w==0],s>=0)
    return cases


def negative_controls():
    r = z3.RealVal
    # Each SAT witness demonstrates loss of recoverability/assumption, not a
    # measured collision rate. These are not final controller benchmarks.
    v,h,b,g = z3.Reals('v h b g')
    normal = [v==10,h==r('.05'),b==r('5.5')]
    def spent(t):
        return v*t+r('2.75')*t*t/2+(v+r('2.75')*t)**2/(2*b)
    return {
        'unguarded_acceleration':normal+[g==v*v/(2*b),spent(h)>g],
        'missed_control_deadline':normal+[g==spent(h),spent(2*h)>g],
        'inadmissible_initial_gap':[v==16,b==r('5.5'),g==1,v*v>2*b*g],
        'backward_obstacle_invalidates_memory':[g==1,g-r('1.5')<0],
        'unbounded_sensor_error_invalidates_lower':[g==10,g+1>g],
    }


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    results={}
    for name,(premises,conclusion) in obligations().items():
        solver=z3.SolverFor('QF_NRA');solver.set(timeout=30000)
        solver.add(*premises,z3.Not(conclusion))
        script=solver.to_smt2();(output/(name+'.smt2')).write_text(script)
        outcome=solver.check()
        results[name]=dict(result=str(outcome),expected='unsat',smt_sha256=hashlib.sha256(script.encode()).hexdigest())
        if outcome!=z3.unsat:
            raise RuntimeError((name,str(outcome),solver.reason_unknown() if outcome==z3.unknown else str(solver.model())))
    controls={}
    for name,premises in negative_controls().items():
        solver=z3.SolverFor('QF_NRA');solver.add(*premises);outcome=solver.check()
        (output/(name+'.smt2')).write_text(solver.to_smt2())
        if outcome!=z3.sat:raise RuntimeError((name,str(outcome)))
        controls[name]=dict(result='sat',expected='sat',witness=str(solver.model()))
    report=dict(passed=True,solver=z3.get_version_string(),obligations=results,negative_controls=controls,
        scope='real arithmetic obligations; analytical flow lemma; not source-code or 2-D plant verification')
    (output/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
