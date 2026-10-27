"""Attribute recorded misses and discarded actions; do not change pass criteria."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    old=ROOT/'docs/research/reviewer-history-v5';timing={}
    def quant(rows,key):
        x=np.array([int(r[key]) for r in rows])/1e6
        return dict(p50_ms=float(np.median(x)),p99_ms=float(np.quantile(x,.99)),max_ms=float(x.max()))
    for f in sorted((old/'kit-smoke').glob('*-ticks.csv')):
        rows=list(csv.DictReader(f.open()));miss=[r for r in rows if r['deadline_miss']=='True']
        timing[f.stem]=dict(ticks=len(rows),misses=len(miss),already_late_at_release=sum(int(r['release_ns'])>=int(r['target_ns'])+10000000 for r in miss),
            missed_with_processing_under_1ms=sum(int(r['control_ns'])<1000000 for r in miss),
            release=quant(rows,'release_lateness_ns'),processing=quant(rows,'control_ns'),thread_cpu=quant(rows,'control_cpu_ns'))
    cases={}
    for f in sorted((old/'pair-0/traces').glob('*-nohistory.csv.gz')):
        with gzip.open(f,'rt') as stream:rows=list(csv.DictReader(stream))
        scenario=f.name.split('-')[-2]
        x=cases.setdefault(scenario,dict(ticks=0,submitted=0,discarded=0,accepted=0))
        x['ticks']+=len(rows);x['submitted']+=sum(r['submitted']=='True' for r in rows)
        x['discarded']+=sum(r['submitted']!='True' for r in rows);x['accepted']+=sum(r['reason']=='accepted' for r in rows)
    result=dict(timing=timing,recorded_development_actions=cases,
        interpretation='Offline traces already evaluate only submitted queries; fixed-tick PPO training samples at all ticks. Discarded actions do not affect plant but add actor updates/entropy. Removing those terms is a variance/credit hypothesis, not a guarantee or proof that baseline gradients are biased. Release misses and wallCPU gaps indicate scheduler/preemption contributions; no unrecorded historical cgroup throttling is attributed to a particular episode.',
        unfixable_from_cloud='No target laptop connection, hardware sensor/actuator or OS hard-real-time reservation available. No deadline threshold or reserved-data change allowed.')
    (a.output/'failure-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
