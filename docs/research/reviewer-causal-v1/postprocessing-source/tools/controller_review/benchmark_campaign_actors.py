"""Matched warm CPU actor timing; no simulation-period or GPU comparison."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_campaign'))
import common
import numpy as np
import torch
from stable_baselines3 import PPO
from causal_student import load_causal
from train import student_folder
from supervisor import P


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    out=args.run/'matched-actor-timing';out.mkdir(exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    affinity=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(affinity)})
    file=sorted((args.run/'development/pair-0/traces').glob('*-lqr.csv.gz'))[0]
    with gzip.open(file,'rt') as handle:
        source=list(csv.DictReader(handle))[:1000]
    observations=np.asarray([[float(row[f'obs{i}']) for i in range(20)] for row in source],dtype=np.float32)
    assert len(observations)==1000
    summary={};rows=[];model_hashes={}
    try:
        for pair,seed in enumerate(P['student_seeds']):
            models={'student':load_causal(student_folder(pair))}
            for arm in P['arms']:
                path=args.run/'training'/f'{arm}-{P["seeds"][pair]}'/'policy.zip'
                ppo=PPO.load(path,device='cpu');model=load_causal(student_folder(pair))
                with torch.no_grad():
                    for a,b in [(ppo.policy.mlp_extractor.policy_net[0],model.net[0]),
                                (ppo.policy.mlp_extractor.policy_net[2],model.net[2]),
                                (ppo.policy.action_net,model.net[4])]:
                        b.weight.copy_(a.weight);b.bias.copy_(a.bias)
                for obs in observations[:50]:
                    action,_=ppo.predict(obs,deterministic=True);residual,_=model.predict(obs)
                    assert abs(P['candidates_rad'][int(action)]-.08*float(residual[0]))<1e-8
                models[arm]=model
                model_hashes[f'{pair}-{arm}']=hashlib.sha256(path.read_bytes()).hexdigest()
            for model in models.values():
                for obs in observations[:100]:model.predict(obs)
            rng=np.random.default_rng(53+pair)
            for index,obs in enumerate(observations):
                for name in rng.permutation(list(models)):
                    cpu=time.thread_time_ns();start=time.perf_counter_ns()
                    models[name].predict(obs)
                    elapsed=time.perf_counter_ns()-start;cpu_elapsed=time.thread_time_ns()-cpu
                    rows.append(dict(pair=pair,seed=seed,method=name,index=index,wall_ns=elapsed,thread_cpu_ns=cpu_elapsed))
        for name in models:
            values=[r['wall_ns']/1e6 for r in rows if r['method']==name]
            summary[name]=dict(n=len(values),median_ms=float(np.median(values)),p99_ms=float(np.quantile(values,.99)),
                               max_ms=max(values),samples_ge_10ms=sum(v>=10 for v in values))
    finally:os.sched_setaffinity(0,affinity)
    with gzip.open(out/'samples.csv.gz','wt',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'protocol.json').write_text(json.dumps(dict(warmup_per_actor=100,parity_rows_per_export=50,
        input_trace=str(file.relative_to(args.run)),input_trace_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
        model_hashes=model_hashes,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        execution='All actors share CausalStudent20-64-64-5 Torch CPU wrapper; exact PPO weight export; randomized method order, single core/thread',
        scope='Warm batch1 actor computation only; excludes observer, supervisor, IPC, queue, actuator and startup. Not a full LANS latency or WCET measurement. No100Hz-as-inference assumption.'),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
