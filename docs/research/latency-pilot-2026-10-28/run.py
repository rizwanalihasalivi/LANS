from pathlib import Path
import sys,json,itertools,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/reviewer_v12'))
import study12 as study
from env12 import Env
OUT=Path(__file__).resolve().parent
class Pilot(Env):
 def reset(self,**kw):
  result=super().reset(**kw)
  self.ctrl.compensated=self.source!='raw'
  self._sense()
  return self.obs.copy(),result[1]
 def step_residual(self,residual):
  t=self.tick*.01
  self.service=(.01 if self.profile=='nominal' else ([.01,.04,.02,.1][int(t)//2%4] if self.profile=='variable' else (1. if 3<=t<4 else .02)))
  return super().step_residual(residual)
def make(case,source,scenario):
 e=Pilot(case=case,source=source,scenario='nominal');e.profile=scenario;return e
study.make_env=make
protocol=dict(scope='Development software-plant pilot; no retraining, no CPU timing or actuator command delay claims',speed=20,paths=['sine120'],mirrors=[-1,1],profiles=['nominal','variable','stall'],sources=['lqr','raw','compensated','student'],noise_base=1986102800,actor_pair=0,ppo='v12 prior-0',freshness_s=.05)
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
models={}
for source,name in [('raw','prior'),('compensated','prior'),('student','student')]:
 p=ROOT/f'docs/research/ppo-audit-v12/actors/{name}-0.npz'
 with np.load(p) as f:models[source]={k:f[k].copy() for k in f.files}
rows=[]
for sign,profile in itertools.product(protocol['mirrors'],protocol['profiles']):
 for source in protocol['sources']:
  name=f'{sign}-{profile}-{source}';p=OUT/(name+'.json');trace=OUT/(name+'.npz')
  if p.exists():
   row=json.loads(p.read_text());assert hashlib.sha256(trace.read_bytes()).hexdigest()==row['trace_sha256']
  else:
   row=dict(mirror=sign,profile=profile,source=source,**study.episode((20,'sine120',sign,'nominal',1986102800),source,profile,models.get(source),trace))
   p.write_text(json.dumps(row,indent=2))
  rows.append(row);print(name,row['rmse_m'],flush=True)
summary=[]
for profile in protocol['profiles']:
 base=[r for r in rows if r['profile']==profile and r['source']=='lqr']
 for source in protocol['sources']:
  rr=[r for r in rows if r['profile']==profile and r['source']==source]
  avg=lambda rs,k:float(np.mean([r[k] for r in rs]))
  summary.append(dict(profile=profile,source=source,tracking_gain_pct=100*(1-avg(rr,'rmse_m')/avg(base,'rmse_m')),rate_change_pct=100*(avg(rr,'rate_rms_rad_s')/avg(base,'rate_rms_rad_s')-1),survived=sum(r['survived'] for r in rr),active_ticks=sum(r['active_ticks'] for r in rr)))
(OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
