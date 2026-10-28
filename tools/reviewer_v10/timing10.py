"""Serialized guard A/B on the revised controller; original deadlines remain."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'tools/reviewer_v10'))
import runtime10 as runtime
from timing_interface4 import Context

def stats():return {k:(Path('/sys/fs/cgroup')/k).read_text() for k in ('cpu.max','cpu.stat')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run/'timing';out.mkdir(parents=True,exist_ok=False)
    decision=json.loads((a.run/'decision.json').read_text());selected=None;arm='causal_history'
    profile='audited_history_comp_v10'
    models=ROOT/'docs/research/reviewer-pipeline-v9/runtime-actors'/arm
    allowed=os.sched_getaffinity(0);cpus=sorted(allowed)[-2:][::-1];assert len(cpus)==2;ctx=Context(cpus[1])
    files=[Path(__file__),ROOT/'tools/reviewer_v10/verify_runtime10.py',Path(runtime.__file__),ROOT/'tools/reviewer_v10/verify_laptop10.py',ROOT/'tools/controller_review/native_heartbeat4.c',ROOT/'tools/reviewer_v8/recovery8.py',ROOT/'tools/reviewer_v8/expiry_cost8.py',ROOT/'tools/reviewer_v7/compensation.py']
    protocol=dict(profile=profile,development_selected=selected,platform_diagnostic=selected is None,models=str(models.relative_to(ROOT)),
        seeds=[701,802,903],seconds=1,cases=list(runtime.CASES),guards=['on'],reserve_ns=1000000,noise_base=1616000000,cpus=cpus,
        hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},model_manifest_sha256=hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest(),cgroup_before=stats())
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    for f in files:
        target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    heart=[];episodes=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in protocol['seeds']:
            order=['on']
            for guard in order:
                folder=out/guard/f'seed-{seed}';folder.mkdir(parents=True)
                rr=[runtime.episode(ctx,case,seed,profile,1,models,folder,external_fault=True,noise_base=protocol['noise_base'],budget_guard=guard=='on') for case in protocol['cases']]
                result=dict(episodes=rr,functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in rr),observed_timing_pass=all(r['deadline_misses']==0 for r in rr))
                (folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n');episodes.extend(dict(guard=guard,**r) for r in rr)
    finally:os.sched_setaffinity(0,allowed)
    summary=dict(heartbeat=heart,profiles={},episodes=episodes,cgroup_after=stats(),guaranteed_realtime=False)
    for guard in ('on',):
        rr=[r for r in episodes if r['guard']==guard]
        summary['profiles'][guard]=dict(ticks=sum(r['ticks'] for r in rr),misses=sum(r['deadline_misses'] for r in rr),functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in rr),observed_timing_pass=all(r['deadline_misses']==0 for r in rr))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
