"""Fixed A/B timer/priority diagnosis; never rebases or forgives10ms deadlines."""
import argparse
import ctypes
import gzip
import csv
import hashlib
import inspect
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_followup'))
import boot
from filtered import FilteredController
import realtime_optimized as runtime
from realtime_campaign_partition import PinnedProcess

ORIGINAL_BURN=runtime.burn
EPISODE_SOURCE=inspect.getsource(runtime.episode)


def burn_worker(stop,cpu):ORIGINAL_BURN(stop,int(os.environ['LANS_TIMING_WORKER_CPU']))


class PriorityProcess(PinnedProcess):
    def __init__(self,p,cpu,nice):super().__init__(p,cpu);self.nice=nice
    def start(self):
        super().start()
        os.setpriority(os.PRIO_PROCESS,self.process.pid,self.nice)


class Context:
    def __init__(self,ctx,cpu):self.ctx,self.cpu=ctx,cpu
    def __getattr__(self,name):return getattr(self.ctx,name)
    def Process(self,*args,**kwargs):
        nice=19 if kwargs.get('target')==burn_worker else 10
        return PriorityProcess(self.ctx.Process(*args,**kwargs),self.cpu,nice)


class Gate:
    def __init__(self,config):self.ctrl=FilteredController('age_filtered')
    @property
    def weight(self):return self.ctrl.weight
    @property
    def good(self):return self.ctrl.good
    def reset(self,baseline,reason,j0=float('nan'),j1=float('nan')):
        self.ctrl.weight=0.;self.ctrl.good=0;self.ctrl.filtered=0.;self.ctrl.last_command=baseline
        return baseline,0.,reason,j0,j1
    def choose(self,t,baseline,packet,estimate,actuator,speed,curvature,gain,role):
        if role!='residual':raise ValueError(role)
        self.ctrl.packet=packet
        command,reason=self.ctrl.choose(t,baseline,estimate,actuator,speed,curvature,gain)
        return command,self.ctrl.weight,'earned' if reason=='age_filtered' else reason,float('nan'),float('nan')


def main():
    p=argparse.ArgumentParser();p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    native_source=ROOT/'tools/controller_review/deadline_wait.c';library=args.output/'deadline_wait.so'
    subprocess.run(['gcc','-std=c11','-O2','-fPIC','-shared',str(native_source),'-o',str(library)],check=True)
    native=ctypes.CDLL(str(library.resolve()));native.lans_monotonic_ns.restype=ctypes.c_int64
    native.lans_wait_until.argtypes=[ctypes.c_int64,ctypes.c_int64];native.lans_wait_until.restype=ctypes.c_int
    # Check clock domain and never-early behavior, not a jitter success test.
    offsets=[]
    for _ in range(40):
        before=time.perf_counter_ns();value=native.lans_monotonic_ns();after=time.perf_counter_ns()
        assert before<=value<=after
        target=after+500000;assert native.lans_wait_until(target,100000)==0
        assert time.perf_counter_ns()>=target
        offsets.append(after-before)
    affinity=os.sched_getaffinity(0);cpus=sorted(affinity)[:2]
    if len(cpus)<2:raise ValueError('Two CPUs required')
    os.environ['LANS_TIMING_WORKER_CPU']=str(cpus[1])
    ctx=Context(mp.get_context('spawn'),cpus[1]);runtime.Gate=Gate;runtime.burn=burn_worker;runtime.CASES['delay1000']=1.
    cases=['nominal','delay1000','cpu_stress','worker_crash'];seeds=[701,802,903];seconds=5.
    sources=[Path(__file__),native_source,ROOT/'tools/reviewer_followup/filtered.py',ROOT/'tools/reviewer_campaign/supervisor.py',
             ROOT/'tools/controller_review/realtime_optimized.py',ROOT/'tools/controller_review/realtime_campaign_partition.py']
    protocol=dict(kind='A/B native absolute-wait and lower-priority worker diagnosis',
        profiles=['sleep','absolute'],seeds=seeds,cases={c:runtime.CASES[c] for c in cases},seconds=seconds,
        period_ms=10,guard_ns=100000,noise_base=1246000000,cpus=cpus,
        controller='predeclared age_filtered; fixed old25k PPO export; no selected-winner claim',
        priority='local nice0; worker nice10; two stress nice19 on worker CPU, including startup',
        randomization='Each seed permutes sleep/absolute with random.Random(1731+seed); same canonical physical noise per seed',
        source_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
        library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),clock_checks=40,
        limits='Wall-paced fixed-step software plant, finite cloud observations, no WCET or physical100Hz guarantee; any deadline miss fails observed strict timing')
    (args.output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    results={name:[] for name in protocol['profiles']}
    def wait_until(target):
        result=native.lans_wait_until(target,100000)
        if result:raise OSError(result,'absolute wait failed')
    runtime.wait_until=wait_until
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in seeds:
            profiles=['sleep','absolute'];random.Random(1731+seed).shuffle(profiles)
            for name in profiles:
                folder=args.output/name;folder.mkdir(exist_ok=True)
                generated=EPISODE_SOURCE.replace('rows.append(row)',"row['filtered_residual']=gate.ctrl.filtered\n            rows.append(row)")
                if name=='absolute':
                    assert 'if wait>0:time.sleep(wait)' in generated
                    generated=generated.replace('if wait>0:time.sleep(wait)','wait_until(target)')
                (folder/'executed-episode.py').write_text(generated)
                exec(compile(generated,str(folder/'executed-episode.py'),'exec'),runtime.__dict__)
                for case in cases:
                    result=runtime.episode(ctx,seed,case,seconds,folder,cpus,args.models,protocol['noise_base'])
                    path=folder/f'{seed}-{case}-ticks.csv.gz'
                    with gzip.open(path,'rt') as handle:rows=list(csv.DictReader(handle))
                    result['nonzero_correction_ticks']=sum(abs(float(r['command'])-float(r['baseline']))>1e-10 for r in rows)
                    for r in rows:
                        weight=float(r['weight']);baseline=float(r['baseline']);command=float(r['command']);residual=float(r['filtered_residual'])
                        assert abs(command-max(-.5,min(.5,baseline+weight*residual)))<1e-12
                    results[name].append(result)
    finally:os.sched_setaffinity(0,affinity)
    for name,episodes in results.items():
        folder=args.output/name
        subprotocol=dict(protocol,seeds=seeds,model_root=str(args.models.resolve()),
            model_hashes={str(seed):hashlib.sha256((args.models/str(seed)/'student.pt').read_bytes()).hexdigest() for seed in seeds})
        (folder/'protocol.json').write_text(json.dumps(subprotocol,indent=2)+'\n')
        summary=dict(episodes=episodes,functional_pass=all(e['survived'] and e['fallback_violations']==0 and e['stale_authority_violations']==0 and e['late_authority_violations']==0 for e in episodes),
                     timing_pass=all(e['deadline_misses']==0 for e in episodes),ticks=sum(e['ticks'] for e in episodes),
                     deadline_misses=sum(e['deadline_misses'] for e in episodes))
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(name,'misses',summary['deadline_misses'],'/',summary['ticks'],flush=True)


if __name__=='__main__':main()
