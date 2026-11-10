"""Fixed-release pacing and reversible affinity for owned control processes.

These reduce avoidable jitter; no OS scheduling or WCET guarantee is implied.
"""
from contextlib import contextmanager
import os,time


class Schedule:
    def __init__(self,period=.05,spin_s=.0015,clock=time.monotonic,sleep=time.sleep):
        if not 0<=spin_s<period:raise ValueError('spin allowance must be within the period')
        self.period,self.spin_s,self.clock,self.sleep=period,spin_s,clock,sleep
        self.origin=clock()

    def target(self,tick):return self.origin+tick*self.period

    def wait(self,tick):
        target=self.target(tick)
        remaining=target-self.clock()
        if remaining>self.spin_s:self.sleep(remaining-self.spin_s)
        while self.clock()<target:self.sleep(0)
        return self.clock()-target


@contextmanager
def control_affinity(processes=()):
    """Pin only this controller and the worker PIDs explicitly owned by it."""
    changes=[];record=dict(applied=False,control_cpu=None,worker_cpus=[],error=None)
    try:
        if hasattr(os,'sched_getaffinity'):
            available=sorted(os.sched_getaffinity(0))
            if len(available)>=2:
                workers=set(available[1:]);record.update(control_cpu=available[0],worker_cpus=sorted(workers))
                for pid,cpus in [(os.getpid(),{available[0]}),*[(p.pid,workers) for p in processes if p is not None and p.is_alive()]]:
                    previous=os.sched_getaffinity(pid)
                    os.sched_setaffinity(pid,cpus);changes.append((pid,previous))
                record['applied']=True
    except OSError as exc:
        record['error']=f'{type(exc).__name__}: {exc}'
    try:yield record
    finally:
        for pid,cpus in reversed(changes):
            try:os.sched_setaffinity(pid,cpus)
            except ProcessLookupError:pass
