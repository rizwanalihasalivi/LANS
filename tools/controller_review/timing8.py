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
import laptop_full_controller as runtime
from timing_interface4 import Context

def stats():return {k:(Path('/sys/fs/cgroup')/k).read_text() for k in ('cpu.max','cpu.stat')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run/'timing';out.mkdir(parents=True,exist_ok=False)
    decision=json.loads((a.run/'decision.json').read_text());selected=decision['selected'];comp=selected!='ppo_raw'
    profile='recovery_compensated' if comp else 'recovery_raw'
    models=ROOT/('docs/research/reviewer-delay-compensation-v7/actor' if comp else 'docs/research/reviewer-history-v5/portable-actor')
    allowed=os.sched_getaffinity(0);cpus=sorted(allowed)[-2:][::-1];assert len(cpus)==2;ctx=Context(cpus[1])
    files=[Path(__file__),ROOT/'tools/controller_review/verify_timing8.py',Path(runtime.__file__),ROOT/'tools/controller_review/verify_full_laptop.py',ROOT/'tools/controller_review/native_heartbeat4.c',ROOT/'tools/reviewer_v8/recovery8.py',ROOT/'tools/reviewer_v8/expiry_cost8.py',ROOT/'tools/reviewer_v7/compensation.py']
    protocol=dict(profile=profile,development_selected=selected,platform_diagnostic=selected is None,models=str(models.relative_to(ROOT)),
        seeds=[701,802,903],seconds=5,cases=list(runtime.CASES),guards=['off','on'],reserve_ns=1000000,noise_base=1486000000,cpus=cpus,
        hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},model_manifest_sha256=hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest(),cgroup_before=stats())
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    for f in files:
        target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    binary=out/'heartbeat';subprocess.run(['gcc','-std=c11','-O2',str(ROOT/'tools/controller_review/native_heartbeat4.c'),'-o',str(binary)],check=True)
    heart=[];episodes=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in protocol['seeds']:
            for case in ('nominal','cpu_stress'):
                stop=ctx.Event();process=None
                if case=='cpu_stress':
                    conn,child=ctx.Pipe();process=ctx.Process(target=runtime.prepared_burn,args=(stop,child));process.start();child.close();assert conn.poll(120) and conn.recv()=='ready';conn.close()
                file=out/f'heartbeat-{seed}-{case}.csv'
                try:subprocess.run([str(binary.resolve()),'500',str(file.resolve())],check=True)
                finally:
                    stop.set()
                    if process is not None:runtime.shutdown(process)
                rr=list(csv.DictReader(file.open()));heart.append(dict(seed=seed,case=case,ticks=len(rr),deadline_misses=sum(r['deadline_miss']=='1' for r in rr)))
        for seed in protocol['seeds']:
            order=['off','on'];random.Random(seed+831).shuffle(order)
            for guard in order:
                folder=out/guard/f'seed-{seed}';folder.mkdir(parents=True)
                rr=[runtime.episode(ctx,case,seed,profile,5,models,folder,external_fault=True,noise_base=protocol['noise_base'],budget_guard=guard=='on') for case in protocol['cases']]
                result=dict(episodes=rr,functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in rr),observed_timing_pass=all(r['deadline_misses']==0 for r in rr))
                (folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n');episodes.extend(dict(guard=guard,**r) for r in rr)
    finally:os.sched_setaffinity(0,allowed)
    summary=dict(heartbeat=heart,profiles={},episodes=episodes,cgroup_after=stats(),guaranteed_realtime=False)
    for guard in ('off','on'):
        rr=[r for r in episodes if r['guard']==guard]
        summary['profiles'][guard]=dict(ticks=sum(r['ticks'] for r in rr),misses=sum(r['deadline_misses'] for r in rr),functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in rr),observed_timing_pass=all(r['deadline_misses']==0 for r in rr))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
