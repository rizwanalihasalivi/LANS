"""Replay exported SMT-LIB files without importing the obligation generator."""
import argparse
import hashlib
import json
from pathlib import Path
import z3


def check(root):
    root=Path(root);report=json.loads((root/'proof.json').read_text())
    assert report['solver']==z3.get_version_string()
    assert len(report['obligations'])==12 and len(report['negative_controls'])==5
    results={}
    for group,expected in (('obligations',z3.unsat),('negative_controls',z3.sat)):
        for name,record in report[group].items():
            path=root/(name+'.smt2')
            if group=='obligations':assert hashlib.sha256(path.read_bytes()).hexdigest()==record['smt_sha256']
            solver=z3.SolverFor('QF_NRA');solver.set(timeout=30000);solver.from_file(str(path))
            outcome=solver.check();assert outcome==expected,(name,str(outcome))
            assert record['result']==record['expected']==str(outcome)
            results[name]=str(outcome)
    return dict(passed=True,exported_scripts=len(results),results=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('proof_root');a=p.parse_args()
    print(json.dumps(check(a.proof_root),indent=2))
