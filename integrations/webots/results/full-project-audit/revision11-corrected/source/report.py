"""Descriptive attribution on correlated shadow decisions; no controller selection."""
import argparse,csv,json,math,statistics,shutil
from pathlib import Path
from collections import defaultdict
HERE=Path(__file__).resolve().parent

def number(row,key):return float(row[key])
def meaningful(delta,base):return delta>max(1e-7,.01*base)
def harmful(delta,base):return delta < -max(1e-7,.01*base)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args();out=a.run
 done=json.loads((out/'complete.json').read_text())
 if done.get('submission_semantics')!='fresh-query-only-v1':
  raise ValueError('Historical run uses re-stamped held proposals; preserve it and run corrected diagnostics into a new directory.')
 rows=list(csv.DictReader((out/'branches.csv').open()));episodes=list(csv.DictReader((out/'episodes.csv').open()))
 assert len(episodes)==done['trajectories']==8;assert len(rows)==done['branch_rows']
 assert len({(r['repetition'],r['region'],r['behavior']) for r in episodes})==8
 grouped=defaultdict(list)
 for r in rows:grouped[(r['repetition'],r['region'],r['behavior'],r['tick'],r['residual_rad'],r['horizon_ticks'])].append(r)
 assert all(sum(r['kind']=='executed' for r in group)==1 for group in grouped.values())
 for group in grouped.values():
  for r in group:
   if r['kind']=='executed' and float(r['weight'])==0:
    assert number(r,'lateral_delta')==0 and number(r,'realized_delta')==0
 text=['# Tire-mismatch gate / objective attribution','',f"Corrected executable freeze: `{done['source_commit']}`. Eight new25m/s DLC220 development trajectories: nominal/tire mismatch × LQR/student behavior × two paired noise repetitions. Current student computes/submits only on50ms query ticks; held packets retain their observation timestamps as in corrected revision10. No policy or gate changes, training, reserved data or production promotion.",'',
 'Each residual has independent shadow gate state along a common behavior trajectory. Available fused commands use that shadow’s prior ramp state. At sampled states, cloned plant/observer branches hold the fused command50ms then use common estimated-state LQR continuation. Actual future noise is used only for offline realized-cost attribution, never action selection or student inference. These are privileged interventions, not deployable teacher results.','',
 '## Trajectory coverage','','| Region | Behavior | Survival /2 | Mean RMSE (m) |','|---|---|---:|---:|']
 for region in ['nominal','tire_mismatch']:
  for behavior in ['lqr','student']:
   subset=[r for r in episodes if r['region']==region and r['behavior']==behavior]
   text.append(f"| {region} | {behavior} | {sum(r['survived']=='True' for r in subset)} | {statistics.mean(float(r['penalized_rmse']) for r in subset):.6f} |")
 text+=['','## 200ms gate decisions','','Counts use meaningful >1% baseline-cost change (absolute floor1e-7). Cost and lateral thresholds are separate. Rejection denominators are state/candidate samples, not independent trials. Helpful safety/recovery withholding is not labelled a cost-model error.','',
 '| Region | Behavior | Accepted | Harmful accepted: combined | Harmful accepted: lateral | Cost rejected | Helpful cost rejected: combined | Helpful cost rejected: lateral | Helpful safety/recovery: lateral |',
 '|---|---|---:|---:|---:|---:|---:|---:|---:|']
 summary=[]
 for region in ['nominal','tire_mismatch']:
  for behavior in ['lqr','student']:
   groups=[g for key,g in grouped.items() if key[1]==region and key[2]==behavior and key[5]=='20']
   accepted=badcost=badlat=rejected=misscost=misslat=safety=0
   for group in groups:
    executed=next(r for r in group if r['kind']=='executed');reason=executed['reason'];allowed=[r for r in group if r['kind']=='available']
    if reason=='earned':
     accepted+=1;badcost+=harmful(number(executed,'realized_delta'),number(executed,'baseline_realized_cost'));badlat+=harmful(number(executed,'lateral_delta'),number(executed,'baseline_lateral_cost'))
    goodcost=any(meaningful(number(r,'realized_delta'),number(r,'baseline_realized_cost')) for r in allowed)
    goodlat=any(meaningful(number(r,'lateral_delta'),number(r,'baseline_lateral_cost')) for r in allowed)
    if reason=='cost':rejected+=1;misscost+=goodcost;misslat+=goodlat
    elif reason!='earned':safety+=goodlat
   summary.append(dict(region=region,behavior=behavior,sampled_candidate_states=len(groups),accepted=accepted,harmful_accepted_combined=int(badcost),harmful_accepted_lateral=int(badlat),cost_rejected=rejected,helpful_cost_rejected_combined=int(misscost),helpful_cost_rejected_lateral=int(misslat),helpful_safety_withheld_lateral=int(safety)))
   text.append(f'| {region} | {behavior} | {accepted} | {badcost} | {badlat} | {rejected} | {misscost} | {misslat} | {safety} |')
 text+=['','## Objective and horizon disagreements','','All available ramp-limited proposals, including correlated duplicate signs/states; comparisons use per-horizon baselines.','',
 '| Region | Proposal comparisons | Combined/lateral opposite meaningful signs at200ms | Helpful lateral200ms → harmful1s | Harmful lateral200ms → helpful1s |',
 '|---|---:|---:|---:|---:|']
 indexed={tuple(r[k] for k in ['repetition','region','behavior','tick','residual_rad','kind','weight','horizon_ticks']):r for r in rows}
 for region in ['nominal','tire_mismatch']:
  subset=[r for r in rows if r['region']==region and r['kind']=='available' and r['horizon_ticks']=='20'];opposite=flip=reverse=0
  for r in subset:
   key=tuple(r[k] for k in ['repetition','region','behavior','tick','residual_rad','kind','weight'])+('100',);long=indexed[key]
   c=number(r,'realized_delta');c0=number(r,'baseline_realized_cost');l=number(r,'lateral_delta');l0=number(r,'baseline_lateral_cost');later=number(long,'lateral_delta');later0=number(long,'baseline_lateral_cost')
   opposite+=(meaningful(c,c0) and harmful(l,l0)) or (harmful(c,c0) and meaningful(l,l0))
   flip+=meaningful(l,l0) and harmful(later,later0);reverse+=harmful(l,l0) and meaningful(later,later0)
  text.append(f'| {region} | {len(subset)} | {opposite} | {flip} | {reverse} |')
 text+=['','## Interpretation limits','',
 'Gate-compatible realized cost uses the same tracking/yaw/effort functional terms and terminal tracking term, with evolving physical path and true scheduled-speed yaw reference. The gate predicts nominal linear physics with local fixed curvature and measured-speed reference. Differences therefore combine model, geometry, estimator and input effects; nominal versus mismatch is contextual evidence, not a clean causal ablation of tire stiffness alone.',
 'The offline branch continuation is LQR, not future teacher/student replanning. Helpful missed interventions are not proof a modified gate would improve whole episodes. Short/long objective sign flips are evidence of local horizon disagreement, not a full explanation of revision10 teacher performance. The full counts include zero candidates and neutral actions. Failed branches are explicitly flagged, combined cost is NaN for failed branches and excluded implicitly from sign tests; lateral costs retain the2.5m tail penalty.',
 'Do not increase PPO authority from these shadow results. A predictor correction or objective revision requires a separately frozen development comparison, preserved survival/nominal/fallback and fresh final evaluation after selection. No5% performance claim follows this diagnostic.']
 (out/'report.md').write_text('\n'.join(text)+'\n');(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 (out/'verification.json').write_text(json.dumps(dict(verified=True,trajectories=8,branch_rows=len(rows),sample_groups=len(grouped),trajectory_survivors=sum(r['survived']=='True' for r in episodes),failed_branch_rows=sum(r['failed_baseline']=='True' or r['failed_candidate']=='True' for r in rows),rejected_execution_equals_baseline=True,actual_future_noise='offline privileged attribution only',final_test_used=False),indent=2)+'\n')
 (out/'source').mkdir(exist_ok=True)
 for name in ['run.py','protocol.json','report.py','test_attribution.py']:shutil.copyfile(HERE/name,out/'source'/name)
if __name__=='__main__':main()
