"""Reject semantic corruptions of aggregates, source wires and motion after rehash."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from .audit import check_python_episode,check_native_episode,sha,read,rows
from .certify import native_refinement


def run(python,native):
    python,native=Path(python),Path(native)
    first_py=read(python/'development/summary.json')['results'][0]
    first_nat=read(native/'development/summary.json')['results'][0]
    results={}
    for kind,root,stored in [('aggregate',python,first_py),('wire',native,first_nat),
                             ('motion',native,first_nat),('intersample_motion',native,first_nat),
                             ('actuator_readback',native,first_nat)]:
        with tempfile.TemporaryDirectory(prefix='lans-settling-tamper-',dir='/tmp') as tmp:
            record=copy.deepcopy(stored);name=f"{stored['case']}-{stored['speed']:g}-{stored['seed']}"
            path=Path(tmp)/name;shutil.copytree(root/'development'/name,path)
            if kind=='aggregate':
                record['tail_spacing_rms_m']=123.
                (path/'summary.json').write_text(json.dumps(record))
                check=lambda:check_python_episode(path,record)
            elif kind in ('wire','actuator_readback'):
                trace=rows(path/'follower.jsonl')
                if kind=='wire':
                    event=next(e for z in trace for e in z['radio_incoming'] if 'state' in json.loads(e['message']))
                    wire=json.loads(event['message']);wire['state'][0]+=.123;event['message']=json.dumps(wire)
                else:
                    row=next(z for z in trace if z['actuation']['emergency'])
                    row['applied_cruise_m_s']+=1.
                p=path/'follower.jsonl';p.write_text(''.join(json.dumps(z)+'\n' for z in trace))
                record['raw_sha256']['follower']=sha(p)
                (path/'verification.json').write_text(json.dumps(record))
                check=lambda:check_native_episode(path,record)
            else:
                p=path/'follower-motion.jsonl';motion=rows(p)
                corrupt_time=1.01 if kind=='intersample_motion' else 1.
                point=next(z for z in motion if abs(z['time_s']-corrupt_time)<1e-8)
                point['position'][0]+=1.
                p.write_text(''.join(json.dumps(z)+'\n' for z in motion))
                record['motion_sha256']['follower']=sha(p)
                (path/'verification.json').write_text(json.dumps(record))
                spec=read(path/'config.json');traces={n:rows(path/f'{n}.jsonl') for n in spec['starts']}
                check=lambda:native_refinement(path,spec,traces)
            try:check()
            except AssertionError:results[kind+'_rejected_after_rehash']=True
            else:raise RuntimeError('Semantic corruption accepted: '+kind)
    return dict(passed=True,checks=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',required=True);p.add_argument('--native',required=True);a=p.parse_args()
    print(json.dumps(run(a.python,a.native),indent=2))
