# Recovered historical PPO: diagnosis, repairs and fixed-budget retest

This is a development experiment on the original three paired policies, not a final controller promotion. Original records and reserved tests remain unchanged.

## Historical recovery

All 144 original LQR/PPO/student episodes and 187,200 transitions reproduce. Original PPO gain is 7.6848456%, with actuator-rate RMS +83.2976%. Student tracking gain was 8.1138673%; its smoothness also failed (+84.24%). These are means on the old 20m/s grid, not improvements in every scenario.

## What the audit found

- Deployment mismatch: the old PPO was trained inside predictive admission, but the recovered gain was measured inside the age-only latency controller. That controller admits fresh discrete residuals with weight up to0.5 and no smoothing.
- Metric mismatch: the old reward penalized changes in commanded steering, whereas the reported smoothness criterion is RMS of actual actuator motion. These are related but not equivalent under lag and slew limits.
- In archived traces the PPO correction could jump0.08rad; actuator slew saturation occupied10.87% of ticks versus0.96% for LQR. The student also saturated frequently. This supports an authority/smoothness problem rather than a PPO-only implementation defect.
- PPO differed from its student on1,507 of40,560 identical input queries (3.72%). This describes policy drift, not proof that each different action is worse. The old objective and supervisor do not directly optimize beating the student after deployment.
- Latency gain nearly removes assistance already at10ms (weight~0.00916) and20ms (~0.00000307). Zero-service nominal results cannot establish real-worker latency performance. The fresh poll10 diagnostic makes this limitation explicit.

## Isolated changes

Low-pass filtering (tau0.15s, unchanged0.5 maximum authority) is evaluated separately. The budget wrapper adds an analytic one-step actuator prediction and projects toward same-state LQR when its predicted absolute rate exceeds1.02times the LQR prediction. This is a local nominal constraint, not a guarantee about episode RMS or vehicle safety.

Two matched100k-step continuations per pair train within the budget wrapper: legacy command-change reward versus actual actuator-rate reward. Both use submitted-request actor credit, a lossless actor/critic bridge for causal filter history, valid terminal observations, and identical seeds, budgets and baselines. Exactly600k additional steps; final endpoints only. Hyperparameters and the fresh matrix were frozen before these outcomes.

## Fresh matched comparison

Three paired models ×15/20/25m/s ×two paths ×both mirrors ×five service/plant conditions ×12methods =2,160episodes. Gains below are ratios of mean episode RMSE. Positive heading/rate changes are worse.

| Method | Tracking gain vs LQR | Heading change | Actuator-rate RMS change | Survived |
|---|---:|---:|---:|---:|
| lqr | 0.0000% | +0.000% | +0.000% | 180/180 |
| original_ppo | 2.8508% | +3.101% | +62.151% | 180/180 |
| original_student | 4.0966% | +2.910% | +63.473% | 180/180 |
| oldfiltered_ppo | 3.3314% | -0.601% | +21.139% | 180/180 |
| lowpass_ppo | 5.6541% | +1.018% | +25.041% | 180/180 |
| lowpass_student | 5.8364% | +1.264% | +25.485% | 180/180 |
| budget_ppo | -3.4488% | +5.636% | +26.325% | 179/180 |
| budget_student | -3.8955% | +5.890% | +27.136% | 179/180 |
| budget_negative | -22.4453% | +1.936% | +0.885% | 180/180 |
| budget_positive | -22.4453% | +1.936% | +0.885% | 180/180 |
| budget_legacy | -5.8541% | +3.798% | +21.375% | 179/180 |
| budget_physical | 2.2528% | +1.956% | +12.800% | 180/180 |

## Selection checks

- **budget_ppo**: lqr: -3.4488%, budget_student: +0.4300%, budget_negative: +15.5143%, budget_positive: +15.5143%. Failed checks: tracking, heading, rate, survival, paired_student. Full development screen: FAIL. User20%target: FAIL.
- **budget_legacy**: lqr: -5.8541%, budget_student: -1.8851%, budget_negative: +13.5499%, budget_positive: +13.5499%. Failed checks: tracking, rate, survival, paired_student. Full development screen: FAIL. User20%target: FAIL.
- **budget_physical**: lqr: +2.2528%, budget_student: +5.9178%, budget_negative: +20.1707%, budget_positive: +20.1707%. Failed checks: rate, paired_student. Full development screen: FAIL. User20%target: FAIL.

## Scenario diagnostics

| Scenario | Original PPO gain | Budget original PPO gain | Retrained legacy gain | Retrained physical gain |
|---|---:|---:|---:|---:|
| nominal | +3.1102% | +8.5037% | +5.4162% | +4.2269% |
| tire | +6.0053% | -12.9642% | -18.1314% | +4.1547% |
| poll10 | +0.8401% | +0.3291% | +0.3202% | +0.3085% |
| delay20 | +0.0002% | +0.0001% | +0.0001% | +0.0001% |
| delay100 | +0.0000% | +0.0000% | +0.0000% | +0.0000% |

## Evidence and limits

Full replay checked 2,913,042 transitions and 1,572,762 actor queries; independent recomputation of all episode metrics; 396 exact100ms LQR fallback comparisons. Tensor/NumPy actor agreement is checked on recorded inputs. The contracts also check analytic actuator prediction against an independent numerical solver and exact training resume including Adam, environments, queues, normalization and RNG.

All wrappers, student, fixed signs and both retraining arms are retained. Same-gate student/fixed comparisons isolate the additional learned contribution from improvements caused by the wrapper itself. Detailed per-seed, per-speed and per-scenario metrics are in summary.json; all episode metrics are in episodes.csv.

No new strict wall-clock timing, native Webots, laptop or physical vehicle validation was performed in this experiment. A simulation actuator-rate projection is not a real-time or robust-safety certificate. Reserved confirmation remains unopened. Passing a development screen, if achieved, would still require corresponding-controller timing and independent confirmation.

## Resume / verify

```bash
/workspace/lans-venv/bin/python tools/reviewer_v13/run13.py --publish
```

The runner verifies frozen inputs, loads complete10k-step checkpoints, skips only hash-verified completed episodes, and publishes milestones. With this finite experiment complete, it performs no additional training. `--verify-only` checks the evidence seal; `--replay` repeats all independent checks.
