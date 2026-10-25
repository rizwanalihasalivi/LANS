# Tire-mismatch gate / objective attribution

Corrected executable freeze: `0e4848a38a08c6d1b69b33a675427c068243957a`. Eight new25m/s DLC220 development trajectories: nominal/tire mismatch × LQR/student behavior × two paired noise repetitions. Current student computes/submits only on50ms query ticks; held packets retain their observation timestamps as in corrected revision10. No policy or gate changes, training, reserved data or production promotion.

Each residual has independent shadow gate state along a common behavior trajectory. Available fused commands use that shadow’s prior ramp state. At sampled states, cloned plant/observer branches hold the fused command50ms then use common estimated-state LQR continuation. Actual future noise is used only for offline realized-cost attribution, never action selection or student inference. These are privileged interventions, not deployable teacher results.

## Trajectory coverage

| Region | Behavior | Survival /2 | Mean RMSE (m) |
|---|---|---:|---:|
| nominal | lqr | 2 | 0.076527 |
| nominal | student | 2 | 0.075431 |
| tire_mismatch | lqr | 2 | 0.196380 |
| tire_mismatch | student | 2 | 0.196800 |

## 200ms gate decisions

Counts use meaningful >1% baseline-cost change (absolute floor1e-7). Cost and lateral thresholds are separate. Rejection denominators are state/candidate samples, not independent trials. Helpful safety/recovery withholding is not labelled a cost-model error.

| Region | Behavior | Accepted | Harmful accepted: combined | Harmful accepted: lateral | Cost rejected | Helpful cost rejected: combined | Helpful cost rejected: lateral | Helpful safety/recovery: lateral |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | lqr | 58 | 24 | 20 | 374 | 21 | 40 | 8 |
| nominal | student | 34 | 17 | 13 | 394 | 32 | 61 | 6 |
| tire_mismatch | lqr | 49 | 17 | 13 | 377 | 17 | 26 | 7 |
| tire_mismatch | student | 32 | 12 | 11 | 388 | 24 | 26 | 13 |

## Objective and horizon disagreements

All available ramp-limited proposals, including correlated duplicate signs/states; comparisons use per-horizon baselines.

| Region | Proposal comparisons | Combined/lateral opposite meaningful signs at200ms | Helpful lateral200ms → harmful1s | Harmful lateral200ms → helpful1s |
|---|---:|---:|---:|---:|
| nominal | 997 | 56 | 85 | 47 |
| tire_mismatch | 1004 | 23 | 78 | 38 |

## Interpretation limits

Gate-compatible realized cost uses the same tracking/yaw/effort functional terms and terminal tracking term, with evolving physical path and true scheduled-speed yaw reference. The gate predicts nominal linear physics with local fixed curvature and measured-speed reference. Differences therefore combine model, geometry, estimator and input effects; nominal versus mismatch is contextual evidence, not a clean causal ablation of tire stiffness alone.
The offline branch continuation is LQR, not future teacher/student replanning. Helpful missed interventions are not proof a modified gate would improve whole episodes. Short/long objective sign flips are evidence of local horizon disagreement, not a full explanation of revision10 teacher performance. The full counts include zero candidates and neutral actions. Failed branches are explicitly flagged, combined cost is NaN for failed branches and excluded implicitly from sign tests; lateral costs retain the2.5m tail penalty.
Do not increase PPO authority from these shadow results. A predictor correction or objective revision requires a separately frozen development comparison, preserved survival/nominal/fallback and fresh final evaluation after selection. No5% performance claim follows this diagnostic.
