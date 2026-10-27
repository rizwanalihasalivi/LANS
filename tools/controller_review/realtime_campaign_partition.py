"""Predeclared timing diagnosis: move test-generated contention off local core.

Does not hide/replace the original contested-core failures or establish OS-level
isolation/WCET. Same frozen PPO export, observer, supervisor, plant and10ms budget.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_campaign'))
import common
import realtime_optimized as runtime
from runtime_adapter import PredictiveGateAdapter

ORIGINAL_BURN=runtime.burn


def worker_core_burn(stop, cpu):
    ORIGINAL_BURN(stop,int(os.environ['LANS_PARTITION_WORKER_CPU']))


class PartitionContext:
    def __init__(self,ctx,cpu):self.ctx,self.cpu=ctx,cpu
    def __getattr__(self,name):return getattr(self.ctx,name)
    def Process(self,*args,**kwargs):
        process=self.ctx.Process(*args,**kwargs)
        return PinnedProcess(process,self.cpu)


class PinnedProcess:
    def __init__(self,process,cpu):self.process,self.cpu=process,cpu
    def __getattr__(self,name):return getattr(self.process,name)
    def start(self):
        self.process.start()
        # Proxy rather than modifying Process.__dict__: spawn must be able to
        # pickle the original Process without a local start-function closure.
        os.sched_setaffinity(self.process.pid,{self.cpu})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    before=os.sched_getaffinity(0);cpus=sorted(before)[:2]
    if len(cpus)!=2:raise RuntimeError('Two available CPUs required; no equivalent isolation claim on one CPU')
    seeds=[701,802,903];cases=['nominal','delay1000','cpu_stress'];seconds=5.
    sources=[Path(__file__),ROOT/'tools/controller_review/realtime_optimized.py',
             ROOT/'tools/reviewer_campaign/supervisor.py',ROOT/'tools/reviewer_campaign/runtime_adapter.py',
             ROOT/'tools/controller_review/realtime_kernels.py',ROOT/'tools/controller_review/causal_student.py']
    protocol=dict(kind='Resource partition diagnostic; same10ms deadlines, no rebasing or code tuning',
        seeds=seeds,cases={'nominal':0.,'delay1000':1.,'cpu_stress':0.},seconds=seconds,
        period_ms=10,stale_age_ms=50,cpus=cpus,noise_base=1096000000,model_root=str(args.models.resolve()),
        source_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
        model_hashes={str(seed):hashlib.sha256((args.models/str(seed)/'student.pt').read_bytes()).hexdigest() for seed in seeds},
        manipulation='Local controller on first CPU; PPO worker and BOTH generated stress processes on second CPU, including child imports. Host OS tasks are NOT excluded.',
        criteria='Raw contracts must pass; any deadline miss fails observed strict timing. Original contested-core evidence remains authoritative for that condition.',
        limits='Three seeds x three5s windows; different physical noise namespace, not a paired causal speedup comparison or WCET proof.')
    (args.output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    runtime.Gate=PredictiveGateAdapter;runtime.CASES['delay1000']=1.
    runtime.burn=worker_core_burn
    os.environ['LANS_PARTITION_WORKER_CPU']=str(cpus[1])
    ctx=PartitionContext(mp.get_context('spawn'),cpus[1]);results=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in seeds:
            for case in cases:
                results.append(runtime.episode(ctx,seed,case,seconds,args.output,cpus,args.models,protocol['noise_base']))
    finally:os.sched_setaffinity(0,before)
    functional=all(r['survived'] and r['fallback_violations']==0 and r['stale_authority_violations']==0
                   and r['late_authority_violations']==0 for r in results)
    for r in results:
        if r['case']=='delay1000':assert r['paired_lqr_max_command_difference']==0
    summary=dict(episodes=results,functional_pass=functional,
                 timing_pass=all(r['deadline_misses']==0 for r in results),
                 limitations=protocol['limits'],original_failures_not_replaced=True)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
