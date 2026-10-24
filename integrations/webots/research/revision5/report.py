"""Recompute review diagnostics without changing controllers or thresholds."""
import argparse,csv,json,hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np
from bootstrap import RESEARCH


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();out=a.input
    done=json.loads((out/'complete.json').read_text())
    for name,sha in done['source_hashes'].items():
        assert hashlib.sha256((RESEARCH/name).read_bytes()).hexdigest()==sha,name
    rows=list(csv.DictReader((out/'episodes.csv').open()));audit=list(csv.DictReader((out/'predictor-audit.csv').open()))
    assert len(rows)==504==done['episodes'];assert len(audit)==done['audited_states_candidates']
    assert len({tuple(r[k] for k in ['seed','speed','path','scenario','method']) for r in rows})==504
    methods=list(dict.fromkeys(r['method'] for r in rows));regions=list(dict.fromkeys(r['scenario'] for r in rows))
    text=['# Controller review remediation diagnostics','','Frozen diagnostic protocol: `e058786`. These are development data, not new reserved tests or a training campaign. Historical sources and checkpoints remain unchanged.','',
          '## Paired nonlearned controls','','| Method | Survival /72 | Mean penalized RMSE (m) | Change vs LQR |','|---|---:|---:|---:|']
    means={m:np.mean([float(r['penalized_rmse']) for r in rows if r['method']==m]) for m in methods}
    for m in methods:
        subset=[r for r in rows if r['method']==m]
        text.append(f"| {m} | {sum(r['survived']=='True' for r in subset)} | {means[m]:.6f} | {(means[m]/means['lqr']-1)*100:+.3f}% |")
    text+=['','| Region | Method | RMSE (m) | Seed101 change vs LQR | Seed202 change vs LQR |','|---|---|---:|---:|---:|']
    for region in regions:
        for method in methods:
            subset=[r for r in rows if r['scenario']==region and r['method']==method]
            changes=[]
            for seed in ['101','202']:
                value=np.mean([float(r['penalized_rmse']) for r in subset if r['seed']==seed])
                base=np.mean([float(r['penalized_rmse']) for r in rows if r['scenario']==region and r['method']=='lqr' and r['seed']==seed])
                changes.append((value/base-1)*100)
            text.append(f"| {region} | {method} | {np.mean([float(r['penalized_rmse']) for r in subset]):.6f} | {changes[0]:+.3f}% | {changes[1]:+.3f}% |")
    reference={tuple(r[k] for k in ['seed','speed','path']):float(r['penalized_rmse']) for r in rows if r['method']=='lqr' and r['scenario']=='latency100'}
    for r in rows:
        if r['scenario']=='latency100':assert float(r['penalized_rmse'])==reference[tuple(r[k] for k in ['seed','speed','path'])]
    text+=['','## Predictor audit','','The table counts shadow-gate decisions on common LQR trajectories. These are correlated sampled states, not independent trials or deployed hybrid trajectories. `False reject` means a cost rejection while at least one currently ramp-allowed blend has >1% realized cost benefit. Age/envelope/persistence exclusions are counted separately. `False accept` requires >1% realized harm; small changes are neutral.','',
           '| Method | Sampled states | Accepted | False accepts / accepted | Cost rejects | False rejects / cost rejects | Helpful withheld by safety/recovery |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for method in methods[1:]:
        subset=[r for r in audit if r['method']==method];accepted=sum(r['reason']=='earned' for r in subset);rejected=sum(r['reason']=='cost' for r in subset)
        fa=sum(r['false_accept']=='True' for r in subset);fr=sum(r['false_reject']=='True' for r in subset)
        text.append(f"| {method} | {len(subset)} | {accepted} | {fa}/{accepted} | {rejected} | {fr}/{rejected} | {sum(r['safety_withheld_helpful']=='True' for r in subset)} |")
    text+=['','| Region | Proposal comparisons | Estimated-state delta MAE | True-state predictor delta MAE |','|---|---:|---:|---:|']
    for region in regions[:4]:
        choices=[c for r in audit if r['scenario']==region for c in json.loads(r['choices'])]
        e=np.mean([abs(c['predicted_delta']-c['realized_delta']) for c in choices]);ideal=np.mean([abs(c['ideal_state_predicted_delta']-c['realized_delta']) for c in choices])
        text.append(f'| {region} | {len(choices)} | {e:.8g} | {ideal:.8g} |')
    text+=['','## Interpretation limits','',
        'All fixed signs, zero and a predeclared linear correction are retained. Nonlearned controls use only the same observable errors. A learning-specific benefit requires beating these controls on independent evidence; lower error than LQR alone does not establish that benefit.',
        'The realized cost branches use privileged true-state continuation and actual plant parameters only inside offline diagnostics. Predictor uses nominal linear physics and local curvature; realized branches use nonlinear dynamics, evolving geometry and actuator lag. True-state predictor columns help separate estimation effects from model/geometry mismatch but are not deployed alternatives. No hidden parameters are passed to the frozen gate.',
        'Legacy PPO is a 1M-step model; A is 100k and uses different seed mapping. Their budgets are not matched. The same known development grid is reused deliberately for attribution, not claimed as fresh generalization. The 5% research target remains unmet unless separately demonstrated; these diagnostics do not authorize full training.',
        'No gate settings were tuned, no standalone policy was relabeled as residual, no research policy was trained and no native Webots or final reserved campaign was run. Severe-delay equality is fallback, not a learned win. Small corrected-root and execution-interface smoke models elsewhere are not performance evidence.']
    (out/'report.md').write_text('\n'.join(text)+'\n')
    (out/'verification.json').write_text(json.dumps(dict(verified=True,episodes=len(rows),audited_states_candidates=len(audit),severe_fallback_exact=True,source_hashes_verified=True),indent=2)+'\n')

if __name__=='__main__':main()
