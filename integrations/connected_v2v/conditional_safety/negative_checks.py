"""Independent semantic corruption rejection after replacing ordinary hashes."""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from .audit import check_episode,flow


def run(root):
    root=Path(root);source=root/'development/adversarial_nominal-16-4001'
    results={}
    for kind in ('sensor_containment','unsafe_guard','plant_transition'):
        with tempfile.TemporaryDirectory(prefix='lans-proof-negative-',dir='/tmp') as tmp:
            dst=Path(tmp)/'episode';shutil.copytree(source,dst)
            rows=[json.loads(line) for line in (dst/'ticks.jsonl').read_text().splitlines()]
            if kind=='sensor_containment':
                msg=rows[0]['arrivals'][0]['message'];msg['position']=str(F(msg['position'])+10)
            elif kind=='plant_transition':
                rows[10]['ego_after'][0]=str(F(rows[10]['ego_after'][0])+1)
            else:
                spec=json.loads((dst/'case.json').read_text());c={k:F(v) for k,v in spec['contract'].items()}
                for row in rows:
                    cert=row['certificate'];X,V,B=map(F,(cert['x'],cert['v'],cert['boundary']))
                    u=c['maximum_command'];xn,vn=flow(X,V,u+c['uncertainty'],c['horizon'])
                    slack=2*c['brake']*(B-X-c['margin'])-2*c['brake']*(xn-X)-vn*vn
                    if slack<0:
                        row['command']=str(u)
                        cert.update(command=str(u),upper_accel=str(u+c['uncertainty']),
                            displacement=str(xn-X),next_v=str(vn),next_x=str(xn),guard_slack_scaled=str(slack))
                        break
                else:raise AssertionError('negative-control fixture never exercised safety intervention')
            trace=''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows)
            (dst/'ticks.jsonl').write_text(trace)
            summary=json.loads((dst/'summary.json').read_text())
            summary['trace_sha256']=hashlib.sha256(trace.encode()).hexdigest()
            (dst/'summary.json').write_text(json.dumps(summary))
            try:check_episode(dst)
            except AssertionError:results[kind+'_rejected_after_rehash']=True
            else:raise RuntimeError('semantic corruption accepted: '+kind)
    return dict(passed=True,checks=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(run(a.root),indent=2))
