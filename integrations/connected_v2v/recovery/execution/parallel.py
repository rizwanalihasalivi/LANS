"""Run fixed confirmation cases in three independent processes, without tuning."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools
import json
from pathlib import Path
import shutil
from integrations.connected_v2v.demo import digest, write
from integrations.connected_v2v.recovery.campaign import PROTOCOL, ROOT, check, assess
from integrations.connected_v2v.recovery.study import run_episode, SCENARIOS
from integrations.connected_v2v.recovery.controller import METHODS


def task(args):
    path,scenario,method,speed,seed,shift=args
    return run_episode(path,scenario,method,speed,seed,seconds=PROTOCOL['seconds'],shift=shift)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--study',required=True)
    args=parser.parse_args();root=check(args.study)
    assert json.loads((root/'development/gate.json').read_text())['passed'],'Development failed'
    destination=root/'confirmation';destination.mkdir(exist_ok=False)
    execution=root/'execution';execution.mkdir(exist_ok=False)
    shutil.copyfile(__file__,execution/'parallel.py')
    write(execution/'launch.json',dict(workers=3,code_sha256=digest(__file__),
        scientific_protocol_sha256=digest(root/'protocol.json'),
        unchanged='controller, model, gains, gates, seeds, timing, metrics and per-episode replay',
        purpose='independent logical-clock episodes; execution scheduling is not a measured outcome'))
    with ProcessPoolExecutor(max_workers=3) as pool:
        repeats=[]
        for scenario in ['nominal','leader_brake']:
            future=pool.submit(task,(execution/scenario,scenario,'fusion',8.,4101,0.))
            repeats.append((scenario,future))
        for scenario,future in repeats:
            row=future.result()
            expected=json.loads((root/f'development/4101-8-{scenario}-fusion/summary.json').read_text())
            assert row==expected and row['raw_sha256']==expected['raw_sha256'],'Parallel execution changed deterministic evidence'
        write(execution/'determinism.json',dict(passed=True,exact_replayed_cases=2,
            check='All per-case summary fields and complete raw JSONL SHA-256 exactly match serial development'))
        pending=[]
        for seed,speed,scenario,method in itertools.product(PROTOCOL['confirmation_seeds'],PROTOCOL['speeds'],SCENARIOS,METHODS):
            path=destination/f'{seed}-{int(speed)}-{scenario}-{method}'
            pending.append(pool.submit(task,(path,scenario,method,speed,seed,PROTOCOL['confirmation_shift_s'])))
        rows=[]
        for future in as_completed(pending):
            rows.append(future.result())
            if len(rows)%12==0:print('confirmation',len(rows),'of',len(pending),'audited episodes complete',flush=True)
    rows.sort(key=lambda r:(r['seed'],r['speed'],SCENARIOS.index(r['scenario']),METHODS.index(r['method'])))
    write(destination/'summary.json',rows)
    gate=assess(rows);write(destination/'gate.json',gate)
    print(json.dumps(gate,indent=2),flush=True)


if __name__=='__main__':main()
