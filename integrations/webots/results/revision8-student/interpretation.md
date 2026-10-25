# Step2 outcome: supervised corrections pass the bounded pilot screen

The expected-cost teacher uses current true state/plant information, but **does not use the actual future sensor-noise realization**. Its branches average separate zero/antithetic Gaussian forecasts. The deployed-in-simulation student uses only the20 existing observed/history channels. This addresses the future-noise privilege in Step1 without claiming that the teacher is unprivileged or globally optimal.

Data:48,600 train labels from216 episodes,24,300 DEV labels from108 separate episodes; three64×64 supervised classifiers trained20epochs each. Model checkpoints were selected at epochs17/19/15 using DEV regret only. No final evaluation data was used for training or selection. This is supervised classification/cost-sensitive imitation, **not PPO fine-tuning**.

## Fresh paired closed-loop results

| Method | Mean penalized RMSE (m) | Reduction versus LQR | Survived |
|---|---:|---:|---:|
| LQR | 0.084434 | — | 108/108 |
| Predeclared fixed−0.04 correction + gate | 0.083743 | 0.819% | 108/108 |
| Expected-cost teacher + gate (privileged reference) | 0.082551 | 2.231% | 108/108 |
| **Supervised student + gate** | **0.082612** | **2.158%** | **108/108** |
| Previous100k execution-trained PPO + gate | 0.084352 | 0.098% | 108/108 |

The student is **1.351% lower error than the fixed correction** and **2.062% lower than the previous PPO reference** on the same fresh conditions. All three optimization/noise-pair means improve against LQR. The student passes the frozen1% LQR/fixed-correction screen and all regional survival/nominal preservation checks. This is a modest absolute mean RMSE reduction of about1.82mm versus LQR, not a broad performance or safety claim.

Student reductions versus LQR by region: nominal3.589%, tire mismatch1.513%, low friction2.121%, sensor stress3.209%,20ms3.689%,100ms0%. Severe-delay equality is the unchanged fallback behavior, not a learned win.

These results show that a sensor/history-only network can capture useful corrections on the evaluated known task families. Unlike Step1's privileged oracle result, the student tracking numbers come from actual saved neural-network predictions; no true state, teacher costs or future noise is passed into student inference. The teacher can still exceed or lose individual cells to a student because finite noisy-forecast receding selection is not a theoretical upper bound.

## Interpretation limits

- Training/development/evaluation noise and episode groups are disjoint, but path geometries and condition families are known. No unseen-road/domain or native-vehicle generalization was established.
- Student data include the known stress/delay families and privileged supervision; previous PPO used nominal synchronous training. Networks, objectives and training budgets differ. The2.062% comparison is a descriptive pipeline improvement, not a causal proof that imitation alone beats PPO at equal compute/data.
- Mean label accuracy is86.7–87.2%; nonzero-label accuracy is76.5–77.4%. Accuracy is a diagnostic only; the closed-loop survival and error measurements are the relevant result.
- Only three optimization/noise pairs were tested. Passing the pilot spending screen does not establish broad statistical superiority, stability, safety, real-time deadlines or superiority over an independently strong MPC. No new MPC comparison is made in this step.
- The classifier profile is distinct from PPO. The existing production/native PPO worker is not repointed, and no model is automatically promoted. PPO fine-tuning and Step3 were not started.

## Verification

[Generated report](report.md), [decision](decision.json), [dataset arrays/episode groups](data/), [selected students and every epoch](students/), and [all540 paired evaluation rows](evaluation/episodes.csv) are retained. Tests cover independent forecast streams, original actor-feature parity, split separation, and a20-feature-only student interface.

Saved tensor reloads exactly reproduce selected DEV regret and train-fitted normalizations. Twelve original `Sensor`/`Execution`/plant replays reproduce representative teacher, student and previous-PPO trajectories. Saved student predictions were checked against reconstructed original observed inputs; maximum state discrepancy was5.69e-14 in those cases. These are original-object consistency checks, not a new external ARIS verdict or a native simulator test.

**Decision:** Step2 supplies a promising supervised initialization/research controller for a separately frozen next stage. Retain the gate and current physical limits. Stop this experiment at its predeclared endpoint; do not add epochs, labels or tuning based on the final grid, and do not transfer this result into a deployment claim.
