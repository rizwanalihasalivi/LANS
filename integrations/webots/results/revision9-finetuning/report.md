# Step3: bounded PPO from the supervised student

Exact five-logit actor transfer; the original20 sensor/history inputs, fixed train-only standardizer, residual grid, execution gate, physical limits and reward are preserved. Critic and optimizer start fresh. Scratch shares standardization and additional RL budget; it does not share the privileged supervised pretraining budget.

Six jobs completed100k steps each (600k additional RL steps). Checkpoints0/25k/50k/100k were selected only on1188 development episodes, followed by756 fresh-noise evaluation episodes. Every endpoint is reported; no final-test selection.

| Method | Survived /108 | Penalized RMSE (m) | Seed mean SD | Reduction vs LQR | Reduction vs student |
|---|---:|---:|---:|---:|---:|
| lqr | 108 | 0.084307 | 0.000146 | +0.000% | -2.111% |
| fixed_m004 | 108 | 0.083617 | 0.000149 | +0.818% | -1.276% |
| student | 108 | 0.082563 | 0.000142 | +2.068% | +0.000% |
| scratch_selected | 108 | 0.084189 | 0.000219 | +0.139% | -1.969% |
| finetune_selected | 108 | 0.082563 | 0.000142 | +2.068% | +0.000% |
| scratch_100k | 108 | 0.084290 | 0.000150 | +0.020% | -2.091% |
| finetune_100k | 108 | 0.082830 | 0.000079 | +1.752% | -0.323% |

## Development-only checkpoint choice

| Arm | RL seed | Selected steps | Eligible | DEV RMSE |
|---|---:|---:|---|---:|
| scratch | 1701 | 25000 | True | 0.083999 |
| finetune | 1701 | 0 | True | 0.082397 |
| scratch | 1802 | 0 | True | 0.084291 |
| finetune | 1802 | 0 | True | 0.082830 |
| scratch | 1903 | 0 | True | 0.084204 |
| finetune | 1903 | 0 | True | 0.082428 |

Step0 is the frozen student in the finetune arm. Selecting it means retaining the student, not demonstrating a PPO gain. All rejected candidates and reasons are in selection.json.

## Regions: final evaluation

| Region | lqr | fixed_m004 | student | scratch_selected | finetune_selected | scratch_100k | finetune_100k |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 0.062906 | 0.061918 | 0.060555 | 0.062843 | 0.060555 | 0.062906 | 0.060920 |
| tire_mismatch | 0.174936 | 0.173873 | 0.172385 | 0.174902 | 0.172385 | 0.174943 | 0.172894 |
| low_friction | 0.081305 | 0.080619 | 0.079635 | 0.081251 | 0.079635 | 0.081305 | 0.079938 |
| sensor_stress | 0.061098 | 0.060537 | 0.059397 | 0.061079 | 0.059397 | 0.061098 | 0.059664 |
| latency20 | 0.062759 | 0.061917 | 0.060571 | 0.062223 | 0.060571 | 0.062649 | 0.060726 |
| latency100 | 0.062838 | 0.062838 | 0.062838 | 0.062838 | 0.062838 | 0.062838 | 0.062838 |

## Paired seed means

| RL seed | Student | Scratch selected | Finetune selected | Finetune100k | Selected reduction vs student |
|---|---:|---:|---:|---:|---:|
| 1701 | 0.082400 | 0.083981 | 0.082400 | 0.082913 | +0.000% |
| 1802 | 0.082628 | 0.084168 | 0.082628 | 0.082822 | +0.000% |
| 1903 | 0.082662 | 0.084418 | 0.082662 | 0.082755 | +0.000% |

## Frozen success screen

| Check | Pass |
|---|---|
| improves_student_by_1pct | False |
| improves_lqr_by_1pct | True |
| improves_fixed_by_1pct | True |
| all_seed_means_better_than_student | False |
| all_finetune_selections_eligible | True |
| regional_survival | True |
| nominal_preserved | True |
| other_active_regions_preserved | True |

PPO improvement screen passed: **False**. Selected finetune reduction versus selected scratch: **+1.931%**. This initialization comparison includes extra Step2 privileged-label pretraining; it is not an equal-total-compute comparison.

## Interpretation limits

Known path geometries and six known condition families, three optimization/noise pairs. These results do not establish unseen-domain generalization, native timing, real-vehicle safety, or superiority to MPC. No new MPC experiment was run. RMSE averages penalized episode scores; unexecuted failed tails receive2.5m. Latency100ms is exact LQR fallback.

Training samples categorical actions; evaluation uses argmax. The five-class actor remains bounded by the existing gate. Target KL0.01 constrains each PPO update against its rollout policy, not against the original student; cumulative forgetting is possible. Standardization stays fixed and reward normalization continues across chunks. The existing reward was deliberately retained, so a tracking gain is measured rather than assumed from reward.

The protocol stops here regardless of outcome. No extra seeds, hyperparameter retries, teacher losses, gate change or production promotion is included.
