"""Predeclared portable-worker timing, native scheduler context and fair kernel costs."""
import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/reviewer_v4'))
import boot4
from interface4 import P
from aligned import trajectory_cost
from scalar_cost import scalar_cost
import numpy as np
import laptop_full_controller as runtime


class Pinned:
    def __init__(self,process,cpu):self.process,self.cpu=process,cpu
    def __getattr__(self,key):return getattr(self.process,key)
    def start(self):
        self.process.start();os.sched_setaffinity(self.process.pid,{self.cpu});os.setpriority(os.PRIO_PROCESS,self.process.pid,19)


class Context:
    def __init__(self,cpu):self.ctx=mp.get_context('spawn');self.cpu=cpu
    def __getattr__(self,key):return getattr(self.ctx,key)
    def Process(self,*args,**kwargs):return Pinned(self.ctx.Process(*args,**kwargs),self.cpu)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    cfg=P['timing'];available=os.sched_getaffinity(0);cpus=sorted(available)[-2:][::-1]
    if len(cpus)!=2:raise RuntimeError('Two allowed CPUs required')
    ctx=Context(cpus[1]);models=ROOT/'docs/research/reviewer-aligned-v3/portable-actor'
    files=[Path(__file__),Path(runtime.__file__),ROOT/'tools/controller_review/native_heartbeat4.c',
        ROOT/'tools/reviewer_v4/interface4.py',ROOT/'tools/reviewer_v4/scalar_cost.py',ROOT/'tools/reviewer_v4/protocol.json']
    protocol=dict(cfg,cpus=cpus,source_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        actor_manifest_sha256=hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest(),
        cgroup_cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),kernel_benchmark='2000states x3seed blocks, randomized reference/scalar order per identical input, warmed exact equations; timing only the kernel call')
    for f in files:
        target=out/'source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    binary=out/'native_heartbeat';subprocess.run(['gcc','-std=c11','-O2',str(ROOT/'tools/controller_review/native_heartbeat4.c'),'-o',str(binary)],check=True)
    heart=[];profiles={name:[] for name in cfg['profiles']};kernel=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in cfg['seeds']:
            for case in ('nominal','cpu_stress'):
                stop=ctx.Event();stress=None
                if case=='cpu_stress':
                    conn,child=ctx.Pipe();stress=ctx.Process(target=runtime.prepared_burn,args=(stop,child));stress.start();child.close()
                    if not conn.poll(120) or conn.recv()!='ready':raise RuntimeError('heartbeat stress did not become ready')
                    conn.close()
                file=out/f'heartbeat-{seed}-{case}.csv'
                try:subprocess.run([str(binary.resolve()),'500',str(file.resolve())],check=True)
                finally:
                    stop.set()
                    if stress is not None:runtime.shutdown(stress)
                rows=list(csv.DictReader(file.open()));assert len(rows)==500
                assert all(int(r['release_ns'])>=int(r['target_ns']) for r in rows)
                heart.append(dict(seed=seed,case=case,ticks=500,deadline_misses=sum(r['deadline_miss']=='1' for r in rows)))
        # Fair per-input kernel benchmark is outside all real-time windows.
        for block in range(3):
            rng=np.random.default_rng(4731+block)
            for i in range(2000):
                z=rng.normal(size=4)*[.3,.1,.03,.1];a=float(rng.uniform(-.1,.1));v=float(rng.uniform(15,25))
                ks=rng.normal(size=3)*.002;g=np.array([.2,.1,.3,.1]);f,r=rng.uniform(-.08,.08,2);w=float(rng.uniform(0,.25))
                inputs=(z,a,v,ks,g,f,r,w)
                if i==0:trajectory_cost(*inputs);scalar_cost(*inputs)
                names=['reference','scalar'];random.Random(47310000+block*2000+i).shuffle(names)
                values={};times={}
                for name in names:
                    fn=trajectory_cost if name=='reference' else scalar_cost
                    before=time.perf_counter_ns();values[name]=fn(*inputs);times[name]=time.perf_counter_ns()-before
                assert abs(values['reference']-values['scalar'])<=1e-11*max(1.,abs(values['reference']))
                kernel.append(dict(block=block,index=i,reference_ns=times['reference'],scalar_ns=times['scalar']))
        runtime.write_csv(out/'kernel-costs.csv',kernel)
        for seed in cfg['seeds']:
            order=cfg['profiles'].copy();random.Random(4731+seed).shuffle(order)
            for profile in order:
                folder=out/profile/f'seed-{seed}';folder.mkdir(parents=True)
                for case in cfg['cases']:
                    row=runtime.episode(ctx,case,seed,profile,cfg['seconds'],models,folder,
                        external_fault=True,noise_base=cfg['noise_base'])
                    profiles[profile].append(row)
                (folder/'summary.json').write_text(json.dumps(dict(episodes=profiles[profile][-len(cfg['cases']):],
                    scope='fixed-step software plant; no physical timing guarantee'),indent=2)+'\n')
    finally:os.sched_setaffinity(0,available)
    summary=dict(heartbeat=heart,profiles={})
    for name,rows in profiles.items():
        functional=all(r['survived'] and r['fallback_violations']==0 and r['actor_packets']>0 for r in rows if r['case']!='worker_crash')
        functional=bool(functional and all(r['external_fault_event'] is not None and 'error' not in r['external_fault_event'] and r['fallback_violations']==0 and r['survived'] for r in rows if r['case']=='worker_crash'))
        summary['profiles'][name]=dict(ticks=sum(r['ticks'] for r in rows),deadline_misses=sum(r['deadline_misses'] for r in rows),
            observed_timing_pass=all(r['deadline_misses']==0 for r in rows),functional_pass=functional,
            nonzero_correction_ticks=sum(r['nonzero_correction_ticks'] for r in rows))
    summary['kernel']={name:dict(median_ns=float(np.median([r[name+'_ns'] for r in kernel])),p99_ns=float(np.quantile([r[name+'_ns'] for r in kernel],.99))) for name in ('reference','scalar')}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
