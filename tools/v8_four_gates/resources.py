"""Reversible affinity of this job's owner and explicitly owned workers only."""
from contextlib import contextmanager
from pathlib import Path
import os


def choose_cpus():
    available=sorted(os.sched_getaffinity(0));seen=set();selected=[]
    for cpu in available:
        root=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        try:key=((root/'physical_package_id').read_text().strip(),(root/'core_id').read_text().strip())
        except OSError:key=cpu
        if key not in seen:seen.add(key);selected.append(cpu)
        if len(selected)==4:return selected
    if len(available)<4:raise RuntimeError('Four allowed CPUs required for declared owner/physics/solver/inference roles')
    return available[:4]


@contextmanager
def owned_affinity(processes=()):
    cpus=[int(x) for x in os.environ['LANS_RUNTIME_CPUS'].split(',')]
    if len(cpus)!=4 or len(set(cpus))!=4 or min(cpus)<0:raise ValueError('Four distinct declared CPUs required')
    changes=[];record=dict(applied=False,owner_cpu=cpus[0],physics_cpu=cpus[1],solver_cpu=cpus[2],inference_cpu=cpus[3],error=None)
    try:
        targets=[(os.getpid(),{cpus[0]})]
        for i,p in enumerate(processes):
            if p is not None and p.is_alive():targets.append((p.pid,{cpus[2] if i==0 else cpus[3]}))
        for pid,mask in targets:
            before=os.sched_getaffinity(pid);os.sched_setaffinity(pid,mask);changes.append((pid,before))
        record['applied']=True
        yield record
    finally:
        for pid,before in reversed(changes):
            try:os.sched_setaffinity(pid,before)
            except ProcessLookupError:pass
