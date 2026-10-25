"""Report the fixed small diagnostic without selecting or tuning a controller."""
import argparse,csv,itertools,json,statistics,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args();out=a.run
 done=json.loads((out/'complete.json').read_text());p=done['protocol'];rows=list(csv.DictReader((out/'episodes.csv').open()))
 expected=set(itertools.product(map(str,p['repetitions']),p['scenarios'],p['methods']))
 keys=[(r['repetition'],r['scenario'],r['method']) for r in rows]
 assert len(rows)==72==done['episodes'] and len(set(keys))==72 and set(keys)==expected
 for rep in ['0','1']:
  base=next(float(r['penalized_rmse']) for r in rows if r['repetition']==rep and r['scenario']=='latency100' and r['method']=='lqr')
  assert all(float(r['penalized_rmse'])==base and float(r['active_fraction'])==0 for r in rows if r['repetition']==rep and r['scenario']=='latency100')
 text=['# Longer-preview / action-sequence development diagnostic','','Frozen design: `dcf203c`. Seventy-two new closed-loop episodes: one known DLC path at25m/s, six conditions, two paired development noise repetitions, six methods. No training, gate/actuator changes or final-test reuse.','',
       'All proposal policies are queried at most every50ms when the simulated worker accepts a request; held proposals are submitted between queries. This differs from the original revision8 teacher/student call cadence. The current student is remeasured here, not copied from its final evaluation. Teacher has privileged current state/parameters and known future geometry, but forecasts do not use actual future measurement noise.','',
       '| Method | Survival /12 | Mean penalized RMSE (m) | Reduction vs paired LQR |','|---|---:|---:|---:|']
 means={m:statistics.mean(float(r['penalized_rmse']) for r in rows if r['method']==m) for m in p['methods']}
 for m in p['methods']:
  group=[r for r in rows if r['method']==m]
  text.append(f"| {m} | {sum(r['survived']=='True' for r in group)} | {means[m]:.6f} | {100*(1-means[m]/means['lqr']):+.3f}% |")
 text+=['','| Region | Student reduction | Hold200ms reduction | Hold400ms reduction | Sequence400ms reduction |','|---|---:|---:|---:|---:|']
 detail=[]
 for region in p['scenarios']:
  regional={m:statistics.mean(float(r['penalized_rmse']) for r in rows if r['method']==m and r['scenario']==region) for m in p['methods']}
  changes={m:100*(1-v/regional['lqr']) for m,v in regional.items()}
  text.append('| '+region+' | '+' | '.join(f'{changes[m]:+.3f}%' for m in ['student','hold20','hold40','sequence40'])+' |')
  for rep in ['0','1']:
   values={r['method']:float(r['penalized_rmse']) for r in rows if r['scenario']==region and r['repetition']==rep}
   detail.append(dict(region=region,repetition=rep,**{m:100*(1-v/values['lqr']) for m,v in values.items()}))
 text+=['','## Interpretation','',
  'The sequence method is a beam approximation: rank first actions by40-tick held cost, retain two, enumerate five second actions after20ticks, execute only the selected first action and replan. It is not exhaustive, an optimum or a controller ceiling. A longer surrogate horizon can improve predicted branch cost yet worsen closed-loop tracking.',
  'These measurements support only this narrow development slice. Report all outcomes without choosing a design from final evaluation. Do not infer5% broad improvement, learned performance, unseen-domain generalization, native timing or safety. Severe100ms equality is fallback. No additional search/training/promotion follows this diagnostic.']
 (out/'report.md').write_text('\n'.join(text)+'\n');(out/'paired-detail.json').write_text(json.dumps(detail,indent=2)+'\n')
 (out/'verification.json').write_text(json.dumps(dict(verified=True,episodes=72,unique_cells=72,survived=sum(r['survived']=='True' for r in rows),severe_fallback_exact=True,final_test_used=False),indent=2)+'\n')
 source=out/'source';source.mkdir(exist_ok=True)
 for relative in ['revision10/run.py','revision10/protocol.json','revision10/report.py','revision10/test_diagnostic.py','revision8/student.py','revision8/teacher.py','revision7/kernels.py','revision5/execution.py','revision2/gating.py','revision2/plant.py','core.py','comparison.py','comparison-protocol.json']:
  target=source/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE.parent/relative,target)

if __name__=='__main__':main()
