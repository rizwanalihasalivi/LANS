# Step2: expected-cost teacher and supervised student

Teacher uses current privileged state/plant but **no actual future measurement noise**. Future costs average zero and independent antithetic Gaussian forecasts. Student sees only the20 original observed/history features. Five residual classes and frozen gate/physical limits remain unchanged.

## Data and supervised selection

| Split | Episodes | Label rows | Nonzero label fraction | Class counts −.08/−.04/0/+.04/+.08 |
|---|---:|---:|---:|---|
| train | 216 | 48600 | 34.00% | [6485, 874, 32078, 957, 8206] |
| dev | 108 | 24300 | 34.77% | [3314, 540, 15851, 397, 4198] |

Episode/noise IDs are disjoint across train/dev/evaluation. Data come from zero/fixed/random-grid behavior; no final evaluation data or teacher rollout was appended to training. Standardization is train-only. Model selection uses DEV label regret, not closed-loop evaluation scores.

| Optimization seed | Selected epoch /20 | DEV mean normalized regret | DEV label accuracy | Nonzero-label accuracy |
|---|---:|---:|---:|---:|
| 701 | 17 | 0.013349 | 86.75% | 77.11% |
| 802 | 19 | 0.012963 | 86.70% | 77.38% |
| 903 | 15 | 0.013297 | 87.16% | 76.53% |

Accuracy is a supervised diagnostic, not tracking performance. Zero abstention and class imbalance make overall accuracy insufficient.

## Fresh paired closed-loop evaluation

| Method | Survived /108 | Mean penalized RMSE (m) | Seed-mean SD | Reduction vs LQR |
|---|---:|---:|---:|---:|
| lqr | 108 | 0.084434 | 0.000223 | +0.000% |
| fixed_m004 | 108 | 0.083743 | 0.000239 | +0.819% |
| teacher | 108 | 0.082551 | 0.000269 | +2.231% |
| student | 108 | 0.082612 | 0.000275 | +2.158% |
| previous_ppo | 108 | 0.084352 | 0.000159 | +0.098% |

| Region | LQR | Fixed −.04 | Teacher | Student | Previous PPO |
|---|---:|---:|---:|---:|---:|
| nominal | 0.062729 | 0.061740 | 0.060433 | 0.060477 | 0.062633 |
| tire_mismatch | 0.175343 | 0.174414 | 0.172769 | 0.172690 | 0.175228 |
| low_friction | 0.081616 | 0.080906 | 0.079779 | 0.079885 | 0.081544 |
| sensor_stress | 0.061728 | 0.061164 | 0.059447 | 0.059747 | 0.061629 |
| latency20 | 0.062805 | 0.061850 | 0.060492 | 0.060488 | 0.062690 |
| latency100 | 0.062386 | 0.062386 | 0.062386 | 0.062386 | 0.062386 |

## Frozen student screen

| Check | Passed |
|---|---|
| improves_lqr_by_1pct | True |
| improves_fixed_by_1pct | True |
| all_seed_means_better_than_lqr | True |
| regional_survival | True |
| nominal_preserved | True |
| no_active_region_over_1pct_worse | True |

Qualified by the declared screen: **True**. Student reduction vs previous PPO: **+2.062%**; different training data/budget and privileged labels make that a descriptive reference, not an equal-budget causal conclusion.

## Limits and stop

Three supervised optimization/noise pairs and known paths/condition families; no broad generalization or native claim. Teacher uses hidden current state/plant and a finite three-sample200ms counterfactual, so its performance is neither a deployable result nor an absolute ceiling. Future forecasts are independent of actual future draws, but the student still faces current hidden-state/parameter ambiguity.

Mean episode RMSE is failure-penalized at2.5m for unexecuted tails. Every method/scenario/failure remains included. At100ms all methods use stale fallback and match LQR. No teacher/student result is transferred from Step1 without evaluation here.

No further dataset, epochs, search, PPO fine-tuning, production gate change or automatic promotion follows this report. Step3 is not launched.
