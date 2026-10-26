import argparse,csv,itertools,json,hashlib
from pathlib import Path
import numpy as np
from bootstrap import HERE,ROOT
from audit import models,P,CONFIG,write_csv
from comparison import configure_lqr
import evaluation
from robust_gate import RobustGate


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    configure_lqr();evaluation.Gate=RobustGate
    sources={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [HERE/'robust_gate.py',HERE/'robust_run.py',HERE/'robust-protocol.json']}
    (a.output/'protocol.json').write_text((HERE/'robust-protocol.json').read_text())
    rows=[]
    for seed in P['seeds']:
        candidates,_=models(seed)
        for speed,path,region,method in itertools.product(P['speeds'],P['paths'],P['scenarios'],['legacy','A100k']):
            row=evaluation.episode(candidates[method],'gated_residual',seed,speed,path,region,CONFIG,P['noise_base'],None);row['method']=method;rows.append(row)
        print(f'robust seed {seed}: {len(rows)} episodes',flush=True)
    write_csv(a.output/'episodes.csv',rows)
    refs=list(csv.DictReader((ROOT/'results/revision5-audit/episodes.csv').open()))
    text=['# Separate nonlinear model-bank gate comparison','','This is a development-only predictor revision; no policy retraining or hidden plant input.','',
          '| Region | Policy | Frozen gate RMSE | Model-bank gate RMSE | Survived /12 |','|---|---|---:|---:|---:|']
    decisions={}
    for method in ['legacy','A100k']:
        region_changes=[];survival=True
        for region in P['scenarios']:
            subset=[r for r in rows if r['method']==method and r['scenario']==region]
            ref=[r for r in refs if r['method']==method and r['scenario']==region]
            before=np.mean([float(r['penalized_rmse']) for r in ref]);after=np.mean([r['penalized_rmse'] for r in subset]);region_changes.append((region,after/before-1))
            survival=survival and sum(r['survived'] for r in subset)>=sum(r['survived']=='True' for r in ref)
            text.append(f'| {region} | {method} | {before:.6f} | {after:.6f} | {sum(r["survived"] for r in subset)} |')
        seed_improvements=[]
        for seed in P['seeds']:
            conditions=['tire_mismatch','low_friction','sensor_stress']
            before=np.mean([float(r['penalized_rmse']) for r in refs if r['method']==method and int(r['seed'])==seed and r['scenario'] in conditions])
            after=np.mean([r['penalized_rmse'] for r in rows if r['method']==method and r['seed']==seed and r['scenario'] in conditions]);seed_improvements.append(after<before)
        exact=all(r['penalized_rmse']==float(next(q['penalized_rmse'] for q in refs if q['method']=='lqr' and all(str(r[k])==q[k] for k in ['seed','speed','path','scenario']))) for r in rows if r['method']==method and r['scenario']=='latency100')
        checks=dict(survival=bool(survival),regional=all(change<=.01 for _,change in region_changes),nominal=dict(region_changes)['nominal']<=.02,both_seed_stress=all(seed_improvements),severe_exact=exact)
        decisions[method]=dict(checks={k:bool(v) for k,v in checks.items()},eligible=bool(all(checks.values())))
    text+=['','## Frozen promotion screen','',json.dumps(decisions,indent=2),'',
        'The model bank uses declared uncertainty values, not true scenario parameters. It still relies on estimated state and approximate local geometry. Lower predictor cost is not a safety guarantee. No model was promoted automatically; the frozen controller and historical results remain unchanged.']
    (a.output/'report.md').write_text('\n'.join(text)+'\n')
    (a.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),sources=sources,decisions=decisions,reserved_evaluated=False),indent=2)+'\n')

if __name__=='__main__':main()
