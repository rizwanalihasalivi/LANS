"""Verify extracted evidence, isolated execution source and integer witnesses."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from .package import verify


def read(p):return json.loads(Path(p).read_text())


def witness_inventory(extract):
    checked=[]
    for suffix,revision,root_name in [('python','v4','settling-v4'),('native','v4','settling-native-v4')]:
        native=suffix=='native'
        for stage,part in [('development','dev'),('validation','validation')]:
            root=extract/'results'/root_name
            certroot=extract/f'results/settling-cert-{suffix}-{part}-{revision}'
            summary=read(certroot/'summary.json')[stage];assert summary['passed']
            pairs=0
            for report in summary['results']:
                case=report['case'];directory=root/stage/case
                spec=read(directory/('config.json' if native else 'case.json'))
                if native:names=set(spec['starts'])
                else:
                    with (directory/'ticks.jsonl').open() as f:first=json.loads(next(f))
                    names={'follower',*first['traffic_before']}
                expected=set(itertools.combinations(sorted(names),2))
                cert=read(certroot/stage/case/'certificate.json')
                assert all(report[k]==v for k,v in cert.items()) and cert['passed']
                path=certroot/stage/case/'witnesses.jsonl.gz'
                assert hashlib.sha256(path.read_bytes()).hexdigest()==cert['witness_sha256']
                count=0;minimum=None;clearance=None
                with gzip.open(path,'rt') as f:
                    for index,line in enumerate(f):
                        row=json.loads(line);assert row['interval']==index
                        assert {(a,b) for a,b,*_ in row['witnesses']}==expected
                        assert len(row['witnesses'])==len(expected)
                        for a,b,nx,ny,lower,upper in row['witnesses']:
                            assert all(isinstance(x,int) for x in (nx,ny,lower,upper))
                            assert abs(nx)+abs(ny)>0 and lower>upper
                            margin=lower-upper;minimum=margin if minimum is None else min(minimum,margin)
                            value=Fraction(margin,abs(nx)+abs(ny))
                            clearance=value if clearance is None else min(clearance,value)
                            pairs+=1
                        count+=1
                assert count==1400 and cert['intervals']==1400
                assert cert['pair_intervals']==count*len(expected)
                assert minimum/1e6==cert['minimum_projection_margin_m']
                assert float(clearance)==cert['minimum_euclidean_clearance_lower_m']
            checked.append(dict(family=suffix,stage=stage,episodes=len(summary['results']),pair_intervals=pairs,passed=True))
    return checked


def isolated_replay(extract,output,native,case):
    root=extract/'results'/('settling-native-v4' if native else 'settling-v4')
    source=root/'source';target=root/'validation'/case
    env=os.environ.copy();env['LANS_V2V_REPO']=str(source)
    # -I ignores the checkout and user import path. Every loaded project module
    # must resolve inside the actual frozen execution snapshot, never live code.
    script='''
import sys,json,pathlib,gzip,itertools
source=pathlib.Path(sys.argv[1]).resolve();sys.path.insert(0,str(source))
native=sys.argv[3]=='native';path=pathlib.Path(sys.argv[2]);certpath=pathlib.Path(sys.argv[4])
if native:
 from integrations.connected_v2v.settling.native import verify
 result=verify(path);assert result['passed']
else:
 from integrations.connected_v2v.settling.study import replay
 result=replay(path);assert result['passed']
from integrations.connected_v2v.settling.trace_certificate import certificate
loaded={}
for name,module in list(sys.modules.items()):
 if name.split('.')[0] in ('controllers','models','integrations') and getattr(module,'__file__',None):
  p=pathlib.Path(module.__file__).resolve();assert p.is_relative_to(source),(name,str(p));loaded[name]=str(p.relative_to(source))
rows=lambda p:[json.loads(l) for l in p.read_text().splitlines()]
if native:
 spec=json.loads((path/'config.json').read_text());traces={n:rows(path/(n+'.jsonl')) for n in spec['starts']}
 # Initial world placement is covered by the complete certificate. Recompute
 # all later intervals here from actual extracted control poses.
 frames=[(traces['follower'][i]['time_s'],{n:z[i]['state'][:3] for n,z in traces.items()}) for i in range(1400)]
else:
 data=rows(path/'ticks.jsonl')
 frames=[(data[0]['time_s'],dict(follower=data[0]['before'][:3],**{n:z[:3] for n,z in data[0]['traffic_before'].items()}))]
 frames += [(r['time_s']+.05,dict(follower=r['after'][:3],**{n:z[:3] for n,z in r['traffic_after'].items()})) for r in data]
with gzip.open(certpath,'rt') as f:witnesses=[json.loads(l) for l in f]
from fractions import Fraction as F
count=0
for i,((t0,a),(t1,b)) in enumerate(zip(frames,frames[1:])):
 row=witnesses[i+1 if native else i]
 expected=[]
 for first,second in itertools.combinations(sorted(a),2):
  c=certificate(a[first],b[first],a[second],b[second],F(str(t1))-F(str(t0)));assert c
  expected.append([first,second,*c['axis'],c['separation_lower_um'],c['occupancy_upper_um']]);count+=1
 assert expected==row['witnesses']
print(json.dumps(dict(passed=True,kind='native stored-input control replay' if native else 'Python stored-input/controller/shared-bicycle replay',case=path.name,project_modules=loaded,recomputed_pair_witnesses=count,physics_rerun=False),indent=2))
'''
    certificate=extract/f"results/settling-cert-{'native' if native else 'python'}-validation-{'v4' if native else 'v4'}/validation/{case}/witnesses.jsonl.gz"
    with (output/(case+('-native' if native else '-python')+'.json')).open('x') as log:
        subprocess.run([sys.executable,'-I','-c',script,str(source),str(target),'native' if native else 'python',str(certificate)],env=env,stdout=log,check=True)


def run(archives,extract,output):
    extract,output=Path(extract),Path(output);output.mkdir(parents=True,exist_ok=False)
    integrity=verify(archives,extract)
    (output/'archive-integrity.json').write_text(json.dumps(integrity,indent=2)+'\n')
    audit=extract/'release-source/integrations/connected_v2v/settling/audit.py'
    def audit_one(job):
        native,name=job
        with (output/(name+'-independent-audit.json')).open('x') as log:
            subprocess.run([sys.executable,'-I',str(audit),str(extract/'results'/name),*(['--native'] if native else [])],stdout=log,check=True)
    # The two independent audits read disjoint frozen cohorts and write distinct logs.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(audit_one,[(False,'settling-v4'),(True,'settling-native-v4')]))
    witnesses=witness_inventory(extract)
    (output/'all-witness-inventory.json').write_text(json.dumps(witnesses,indent=2)+'\n')
    jobs=[(False,'combined-16-9001'),(False,'curved-16-9001'),
          (True,'combined-12-16001'),(True,'curved-12-16001')]
    def replay_one(job):isolated_replay(extract,output,*job)
    # Each replay launches its own isolated interpreter and has a separate output.
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(replay_one,jobs))
    result=dict(passed=True,integrity=integrity,witnesses=witnesses,isolated_source_replays=4,
        scope='extracted bytes, independent audits, all strict integer witnesses, and four source-only control/geometry replays; native physics is not rerun')
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archives',required=True);p.add_argument('--extract',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(run(a.archives,a.extract,a.output),indent=2))
