"""Audit actual stall/return packets and software physical trajectories."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
import verify_full_laptop as verifier

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run;protocol=json.loads((out/'protocol.json').read_text())
    for name,digest in protocol['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    verifier.CASES.clear();verifier.CASES['recover']=0.
    models=ROOT/'docs/research/reviewer-delay-compensation-v7/actor';delayed=0
    for seed in protocol['seeds']:
        folder=out/f'seed-{seed}';sys.argv=['verify_full_laptop.py','--run',str(folder),'--models',str(models)];verifier.main()
        rows=list(csv.DictReader((folder/'recover-ticks.csv').open()));packets=list(csv.DictReader((folder/'recover-packets.csv').open()));first=min(int(r['observed_ns']) for r in packets)
        for r in packets:
            expected=1. if 2.<=(int(r['observed_ns'])-first)/1e9<3. else 0.
            assert float(r['injected_service_s'])==expected and int(r['sent_ns'])-int(r['inferred_ns'])>=round(expected*1e9)
            if expected:
                delayed+=1
                assert all(float(t['weight'])==0 and t['command']==t['baseline'] for t in rows if int(t['packet_seq'])==int(r['seq']))
    assert delayed>=3
    result=dict(actor_timestamp_and_physical_replay=True,actual_one_second_stalls_verified=delayed,source_hashes_verified=True,
        complete_projection_and_recovery_memory_replay=False,scope='Dynamic packet/actor/physical audit; full query/gate-memory replay is separately recorded for the15,000tick timing campaign')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
