"""Report every declared arm; failed criteria remain failed."""
import boot13
import json


def main(out):
    summary=json.loads((out/'summary.json').read_text());decision=json.loads((out/'decision.json').read_text())
    verified=json.loads((out/'verification.json').read_text());recovered=json.loads((out/'recovered.json').read_text())
    rows=['| Method | Tracking gain vs LQR | Heading change | Actuator-rate RMS change | Survived |',
          '|---|---:|---:|---:|---:|']
    for name,m in summary['overall'].items():
        rows.append(f"| {name} | {m['gain_vs_lqr_pct']:.4f}% | {m['heading_change_pct']:+.3f}% | {m['rate_change_pct']:+.3f}% | {m['survived']}/{m['episodes']} |")
    lines=['# Recovered historical PPO: diagnosis, repairs and fixed-budget retest','',
        'This is a development experiment on the original three paired policies, not a final controller promotion. Original records and reserved tests remain unchanged.','',
        '## Historical recovery','',
        f"All {recovered['episodes']} original LQR/PPO/student episodes and {recovered['transitions']:,} transitions reproduce. Original PPO gain is 7.6848456%, with actuator-rate RMS +83.2976%. Student tracking gain was 8.1138673%; its smoothness also failed (+84.24%). These are means on the old 20m/s grid, not improvements in every scenario.",'',
        '## What the audit found','',
        '- Deployment mismatch: the old PPO was trained inside predictive admission, but the recovered gain was measured inside the age-only latency controller. That controller admits fresh discrete residuals with weight up to0.5 and no smoothing.',
        '- Metric mismatch: the old reward penalized changes in commanded steering, whereas the reported smoothness criterion is RMS of actual actuator motion. These are related but not equivalent under lag and slew limits.',
        '- In archived traces the PPO correction could jump0.08rad; actuator slew saturation occupied10.87% of ticks versus0.96% for LQR. The student also saturated frequently. This supports an authority/smoothness problem rather than a PPO-only implementation defect.',
        '- PPO differed from its student on1,507 of40,560 identical input queries (3.72%). This describes policy drift, not proof that each different action is worse. The old objective and supervisor do not directly optimize beating the student after deployment.',
        '- Latency gain nearly removes assistance already at10ms (weight~0.00916) and20ms (~0.00000307). Zero-service nominal results cannot establish real-worker latency performance. The fresh poll10 diagnostic makes this limitation explicit.','',
        '## Isolated changes','',
        'Low-pass filtering (tau0.15s, unchanged0.5 maximum authority) is evaluated separately. The budget wrapper adds an analytic one-step actuator prediction and projects toward same-state LQR when its predicted absolute rate exceeds1.02times the LQR prediction. This is a local nominal constraint, not a guarantee about episode RMS or vehicle safety.',
        '',
        'Two matched100k-step continuations per pair train within the budget wrapper: legacy command-change reward versus actual actuator-rate reward. Both use submitted-request actor credit, a lossless actor/critic bridge for causal filter history, valid terminal observations, and identical seeds, budgets and baselines. Exactly600k additional steps; final endpoints only. Hyperparameters and the fresh matrix were frozen before these outcomes.','',
        '## Fresh matched comparison','',
        'Three paired models ×15/20/25m/s ×two paths ×both mirrors ×five service/plant conditions ×12methods =2,160episodes. Gains below are ratios of mean episode RMSE. Positive heading/rate changes are worse.','',*rows,'',
        '## Selection checks','']
    for name,d in decision.items():
        gains=', '.join(f'{k}: {v:+.4f}%' for k,v in d['gains_pct'].items())
        failures=', '.join(k for k,v in d['checks'].items() if not v) or 'none'
        lines += [f"- **{name}**: {gains}. Failed checks: {failures}. Full development screen: {'PASS' if d['full_screen_pass'] else 'FAIL'}. User20%target: {'PASS' if d['twenty_percent_pass'] else 'FAIL'}."]
    lines += ['', '## Scenario diagnostics','', '| Scenario | Original PPO gain | Budget original PPO gain | Retrained legacy gain | Retrained physical gain |', '|---|---:|---:|---:|---:|']
    for scenario,m in summary['by_scenario'].items():
        b=m['lqr']['rmse_m'];g=[100*(1-m[k]['rmse_m']/b) for k in ('original_ppo','budget_ppo','budget_legacy','budget_physical')]
        lines.append('| '+scenario+' | '+' | '.join(f'{x:+.4f}%' for x in g)+' |')
    lines += ['', '## Evidence and limits','',
        f"Full replay checked {verified['transitions']:,} transitions and {verified['neural_queries']:,} actor queries; independent recomputation of all episode metrics; {verified['exact_fallback_pairs']} exact100ms LQR fallback comparisons. Tensor/NumPy actor agreement is checked on recorded inputs. The contracts also check analytic actuator prediction against an independent numerical solver and exact training resume including Adam, environments, queues, normalization and RNG.",'',
        'All wrappers, student, fixed signs and both retraining arms are retained. Same-gate student/fixed comparisons isolate the additional learned contribution from improvements caused by the wrapper itself. Detailed per-seed, per-speed and per-scenario metrics are in summary.json; all episode metrics are in episodes.csv.',
        '',
        'No new strict wall-clock timing, native Webots, laptop or physical vehicle validation was performed in this experiment. A simulation actuator-rate projection is not a real-time or robust-safety certificate. Reserved confirmation remains unopened. Passing a development screen, if achieved, would still require corresponding-controller timing and independent confirmation.',
        '', '## Resume / verify','',
        '```bash','/workspace/lans-venv/bin/python tools/reviewer_v13/run13.py --publish','```','',
        'The runner verifies frozen inputs, loads complete10k-step checkpoints, skips only hash-verified completed episodes, and publishes milestones. With this finite experiment complete, it performs no additional training. `--verify-only` checks the evidence seal; `--replay` repeats all independent checks.']
    (out/'README.md').write_text('\n'.join(lines)+'\n')
