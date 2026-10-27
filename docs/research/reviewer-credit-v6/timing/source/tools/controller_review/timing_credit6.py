"""Frozen original-target timing campaign, run without concurrent research jobs."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import laptop_full_controller as runtime
from timing_interface4 import Context

def cgroup():
    return {n:(Path('/sys/fs/cgroup')/n).read_text() for n in ('cpu.max','cpu.stat')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args();out=a.output
    out.mkdir(parents=True,exist_ok=False);allowed=os.sched_getaffinity(0);cpus=sorted(allowed)[-2:][::-1];assert len(cpus)==2
    models=a.models.resolve();manifest=models/'manifest.json'
    files=[Path(__file__),Path(runtime.__file__),ROOT/'tools/controller_review/native_heartbeat4.c',ROOT/'tools/controller_review/verify_full_laptop.py',ROOT/'tools/controller_review/verify_timing_credit6.py',ROOT/'tools/reviewer_v4/interface4.py',ROOT/'tools/reviewer_v4/scalar_cost.py',ROOT/'tools/laptop/precision_wait.py']
    protocol=dict(profiles=['fresh_history'],seeds=[701,802,903],cases=list(runtime.CASES),seconds=5,
        source_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},models=str(models.relative_to(ROOT)),
        actor_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),cpus=cpus,noise_base=1446000000,
        scope='No concurrent training/evaluation; software plant only. No retry, deadline shift, skipped-tick forgiveness or hard-real-time guarantee.',cgroup_before=cgroup())
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    for f in files:
        target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    binary=out/'heartbeat';subprocess.run(['gcc','-std=c11','-O2',str(ROOT/'tools/controller_review/native_heartbeat4.c'),'-o',str(binary)],check=True)
    ctx=Context(cpus[1]);heart=[];episodes=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in protocol['seeds']:
            for case in ('nominal','cpu_stress'):
                stop=ctx.Event();stress=None
                if case=='cpu_stress':
                    conn,child=ctx.Pipe();stress=ctx.Process(target=runtime.prepared_burn,args=(stop,child));stress.start();child.close()
                    assert conn.poll(120) and conn.recv()=='ready';conn.close()
                f=out/f'heartbeat-{seed}-{case}.csv'
                try:subprocess.run([str(binary.resolve()),'500',str(f.resolve())],check=True)
                finally:
                    stop.set()
                    if stress is not None:runtime.shutdown(stress)
                rr=list(csv.DictReader(f.open()));heart.append(dict(seed=seed,case=case,ticks=len(rr),deadline_misses=sum(r['deadline_miss']=='1' for r in rr)))
        for seed in protocol['seeds']:
            folder=out/'fresh_history'/f'seed-{seed}';folder.mkdir(parents=True)
            rows=[runtime.episode(ctx,case,seed,'fresh_history',5,models,folder,external_fault=True,noise_base=protocol['noise_base']) for case in protocol['cases']]
            result=dict(episodes=rows,functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in rows),observed_timing_pass=all(r['deadline_misses']==0 for r in rows))
            (folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n');episodes+=rows
    finally:os.sched_setaffinity(0,allowed)
    result=dict(episodes=episodes,heartbeat=heart,ticks=sum(r['ticks'] for r in episodes),deadline_misses=sum(r['deadline_misses'] for r in episodes),
        functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in episodes),observed_timing_pass=all(r['deadline_misses']==0 for r in episodes),
        guaranteed_hard_realtime=False,cgroup_after=cgroup())
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
