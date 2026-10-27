"""Separate prespecified real-worker stall/recovery test, no model or gate tuning."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/reviewer_v4'))
import boot4
import laptop_full_controller as runtime
from timing_interface4 import Context
from precision_wait import DeadlineWaiter
import numpy as np


def recovering_actor(connection,folder,seed,delay):
    first=None
    try:
        portable=runtime.load_portable(folder);portable.golden_check();model=portable.load(seed)
        for _ in range(100):portable.logits(model,np.zeros((1,20),np.float32))
        with DeadlineWaiter('auto') as waiter:
            connection.send(('ready',waiter.backend))
            while True:
                request=connection.recv()
                if request is None:return
                seq,observed,x,*extra=request
                if first is None:first=observed
                entered=time.perf_counter_ns();index=int(portable.logits(model,x[None,:]).argmax(1)[0]);inferred=time.perf_counter_ns()
                injected=1. if 2.<=(observed-first)/1e9<3. else 0.
                if injected:waiter.wait_until_ns(inferred+1000000000)
                message=dict(seq=seq,observed_ns=observed,entered_ns=entered,inferred_ns=inferred,
                    sent_ns=time.perf_counter_ns(),residual=[-.08,-.04,0.,.04,.08][index],observation_json=json.dumps(x.tolist()),
                    injected_service_s=injected,first_observed_ns=first)
                if extra:message['query_metadata_json']=json.dumps(extra[0])
                connection.send(('output',message))
    except (EOFError,BrokenPipeError):pass
    except Exception as error:
        try:connection.send(('error',repr(error)))
        except (EOFError,OSError):pass
    finally:connection.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output
    out.mkdir(parents=True,exist_ok=False)
    import os
    original=os.sched_getaffinity(0);cpus=sorted(original)[-2:][::-1];ctx=Context(cpus[1])
    models=ROOT/'docs/research/reviewer-delay-compensation-v7/actor'
    protocol=dict(profile='recovery_compensated',seeds=[701,802,903],seconds=8,noise_base=1496000000,
        stall='One-second post-inference wait for requests observed in [2,3)s from first request; all later requests healthy again',
        criteria='Raw audits pass; actual long-delayed packet rejected; nonzero assistance exercised both before stall and after healthy return; all stale/late actions use local LQR. Any10ms miss separately fails observed timing. No physical safety guarantee.',
        source_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),Path(runtime.__file__),ROOT/'tools/reviewer_v8/recovery8.py',ROOT/'tools/reviewer_v8/expiry_cost8.py',ROOT/'tools/reviewer_v7/compensation.py')})
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n');runtime.actor=recovering_actor
    episodes=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in protocol['seeds']:
            folder=out/f'seed-{seed}';folder.mkdir();runtime.CASES['recover']=0.
            e=runtime.episode(ctx,'recover',seed,'recovery_compensated',8.,models,folder,noise_base=protocol['noise_base'],budget_guard=True)
            rows=list(csv.DictReader((folder/'recover-ticks.csv').open()));packets=list(csv.DictReader((folder/'recover-packets.csv').open()))
            first=min(int(r['observed_ns']) for r in packets)
            delayed=[r for r in packets if float(r['injected_service_s'])>0]
            assert delayed,'Stall must actually occur, not merely be configured'
            for r in packets:
                expected=1. if 2.<=(int(r['observed_ns'])-first)/1e9<3. else 0.
                assert float(r['injected_service_s'])==expected
                assert int(r['sent_ns'])-int(r['inferred_ns'])>=round(expected*1e9)
            delayed_sequences={int(r['seq']) for r in delayed}
            assert all(float(r['weight'])==0 and r['command']==r['baseline'] for r in rows if int(r['packet_seq']) in delayed_sequences)
            before=[r for r in rows if int(r['apply_ns'])<first+2000000000 and abs(float(r['command'])-float(r['baseline']))>1e-10]
            after=[r for r in rows if int(r['apply_ns'])>=first+3000000000 and abs(float(r['command'])-float(r['baseline']))>1e-10]
            e.update(delayed_packets=len(delayed),assisted_before=len(before),assisted_after=len(after),
                recovery_exercised=bool(before and after),functional_recovery_pass=bool(e['survived'] and e['fallback_violations']==0 and before and after))
            episodes.append(e);(folder/'summary.json').write_text(json.dumps(dict(episodes=[e]),indent=2)+'\n')
    finally:os.sched_setaffinity(0,original)
    (out/'summary.json').write_text(json.dumps(dict(episodes=episodes,functional_recovery_pass=all(e['functional_recovery_pass'] for e in episodes),
        timing_pass=all(e['deadline_misses']==0 for e in episodes),ticks=sum(e['ticks'] for e in episodes),deadline_misses=sum(e['deadline_misses'] for e in episodes)),indent=2)+'\n')


if __name__=='__main__':main()
