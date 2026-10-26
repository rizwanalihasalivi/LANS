import boot3
import argparse
import csv
import ctypes
import gzip
import hashlib
import inspect
import json
import multiprocessing as mp
import os
import random
import subprocess
import time
from realtime_followup import Context,PriorityProcess,Gate,burn_worker
import realtime_optimized as runtime
from aligned import P


class Context3(Context):
    def Process(self,*args,**kwargs):return PriorityProcess(self.ctx.Process(*args,**kwargs),self.cpu,19)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=boot3.Path,required=True);args=p.parse_args();out=args.output
    out.mkdir(parents=True,exist_ok=False);cfg=P['timing'];before=os.sched_getaffinity(0);available=sorted(before)
    if len(available)<2:raise RuntimeError('Two distinct CPUs required')
    cpus=[available[-1],available[-2]];os.environ['LANS_TIMING_WORKER_CPU']=str(cpus[1])
    library=out/'spin_wait.so';subprocess.run(['gcc','-std=c11','-O2','-shared','-fPIC',str(boot3.HERE/'spin_wait.c'),'-o',str(library)],check=True)
    native=ctypes.CDLL(str(library.resolve()));native.lans_monotonic_ns.restype=ctypes.c_int64
    native.lans_wait.argtypes=[ctypes.c_int64,ctypes.c_int];native.lans_wait.restype=ctypes.c_int
    for mode in (0,1):
        for _ in range(20):
            start=time.perf_counter_ns();sample=native.lans_monotonic_ns();end=time.perf_counter_ns();assert start<=sample<=end
            target=end+500000;assert native.lans_wait(target,mode)==0 and time.perf_counter_ns()>=target
    models=boot3.ROOT/'docs/research/reviewer-causal-v1/export'
    source=[boot3.HERE/'timing3.py',boot3.HERE/'spin_wait.c',boot3.HERE/'protocol.json',boot3.ROOT/'tools/controller_review/realtime_followup.py',
        boot3.ROOT/'tools/controller_review/realtime_optimized.py',boot3.ROOT/'tools/controller_review/realtime_kernels.py',boot3.ROOT/'tools/controller_review/causal_student.py',
        boot3.ROOT/'tools/reviewer_followup/filtered.py',boot3.ROOT/'tools/reviewer_campaign/supervisor.py']
    protocol=dict(cfg,cpus=cpus,seconds=cfg['seconds_each'],cases={k:1. if k=='delay1000' else 0. for k in cfg['cases']},
        source_hashes={str(f.relative_to(boot3.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source},
        model_root=str(models),model_hashes={str(s):hashlib.sha256((models/str(s)/'student.pt').read_bytes()).hexdigest() for s in cfg['seeds']},
        cgroup_cpu_max=boot3.Path('/sys/fs/cgroup/cpu.max').read_text().strip(),scheduler_policy=os.sched_getscheduler(0),
        interpretation='Any miss fails observed strict10ms. Full spin consumes one CPU; host not isolated; no WCET/physical safety or laptop default claim.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    original=inspect.getsource(runtime.episode);runtime.Gate=Gate;runtime.burn=burn_worker;runtime.CASES['delay1000']=1.
    ctx=Context3(mp.get_context('spawn'),cpus[1]);results={name:[] for name in cfg['profiles']}
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in cfg['seeds']:
            profiles=cfg['profiles'].copy();random.Random(2731+seed).shuffle(profiles)
            for name in profiles:
                folder=out/name;folder.mkdir(exist_ok=True)
                def wait_until(target):
                    result=native.lans_wait(target,int(name=='dedicated_spin'))
                    if result:raise OSError(result,'native wait failed')
                runtime.wait_until=wait_until
                generated=original.replace('if wait>0:time.sleep(wait)','wait_until(target)').replace('rows.append(row)',"row['filtered_residual']=gate.ctrl.filtered\n            rows.append(row)")
                (folder/'executed-episode.py').write_text(generated);exec(compile(generated,str(folder/'executed-episode.py'),'exec'),runtime.__dict__)
                for case in cfg['cases']:
                    result=runtime.episode(ctx,seed,case,cfg['seconds_each'],folder,cpus,models,cfg['noise_base'])
                    with gzip.open(folder/f'{seed}-{case}-ticks.csv.gz','rt') as f:rows=list(csv.DictReader(f))
                    result['nonzero_correction_ticks']=sum(abs(float(r['command'])-float(r['baseline']))>1e-10 for r in rows)
                    for r in rows:assert abs(float(r['command'])-max(-.5,min(.5,float(r['baseline'])+float(r['weight'])*float(r['filtered_residual']))))<1e-12
                    results[name].append(result)
    finally:os.sched_setaffinity(0,before)
    for name,episodes in results.items():
        folder=out/name;(folder/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
        summary=dict(episodes=episodes,ticks=sum(e['ticks'] for e in episodes),deadline_misses=sum(e['deadline_misses'] for e in episodes),
            timing_pass=all(e['deadline_misses']==0 for e in episodes),functional_pass=all(e['survived'] and e['fallback_violations']==0 and e['stale_authority_violations']==0 and e['late_authority_violations']==0 for e in episodes))
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(name,summary['deadline_misses'],'/',summary['ticks'],flush=True)


if __name__=='__main__':main()
