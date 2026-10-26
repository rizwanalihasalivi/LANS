"""Independent grid, integrity and frozen-screen audit of model-bank evidence."""
import csv,hashlib,itertools,json
import numpy as np
from bootstrap import HERE,ROOT
out=ROOT/'results/revision5-robust';done=json.loads((out/'complete.json').read_text())
for name,sha in done['sources'].items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha
rows=list(csv.DictReader((out/'episodes.csv').open()))
expected=set(itertools.product(['101','202'],['15','20','25'],['sine120','dlc220'],['nominal','tire_mismatch','low_friction','sensor_stress','latency20','latency100'],['legacy','A100k']))
keys=[tuple(r[k] for k in ['seed','speed','path','scenario','method']) for r in rows]
assert len(rows)==144 and set(keys)==expected and len(set(keys))==144
ref=list(csv.DictReader((ROOT/'results/revision5-audit/episodes.csv').open()))
for r in rows:
 assert float(r['max_rate'])<=.3500001
 if r['scenario']=='latency100':
  base=next(q for q in ref if q['method']=='lqr' and all(q[k]==r[k] for k in ['seed','speed','path','scenario']))
  assert r['penalized_rmse']==base['penalized_rmse'] and float(r['active_fraction'])==0
for method in ['legacy','A100k']:
 changes={}
 survival=True
 for region in {r['scenario'] for r in rows}:
  a=[r for r in rows if r['method']==method and r['scenario']==region]
  b=[r for r in ref if r['method']==method and r['scenario']==region]
  changes[region]=np.mean([float(r['penalized_rmse']) for r in a])/np.mean([float(r['penalized_rmse']) for r in b])-1
  survival &= sum(r['survived']=='True' for r in a)>=sum(r['survived']=='True' for r in b)
 stress=['tire_mismatch','low_friction','sensor_stress'];seed_ok=[]
 for seed in ['101','202']:
  a=[float(r['penalized_rmse']) for r in rows if r['method']==method and r['seed']==seed and r['scenario'] in stress]
  b=[float(r['penalized_rmse']) for r in ref if r['method']==method and r['seed']==seed and r['scenario'] in stress]
  seed_ok.append(np.mean(a)<np.mean(b))
 checks=dict(survival=survival,regional=all(x<=.01 for x in changes.values()),nominal=bool(changes['nominal']<=.02),both_seed_stress=all(seed_ok),severe_exact=True)
 assert checks==done['decisions'][method]['checks']
 assert all(checks.values())==done['decisions'][method]['eligible']
result=dict(verified=True,episodes=144,survived=sum(r['survived']=='True' for r in rows),severe_fallback_exact=True,source_hashes_verified=True,decisions_recomputed=True)
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
