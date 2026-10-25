# Student anchor and proposal-credit factorial pilot

Four arms, three matched fresh RL seeds each,100k transitions per job: **1.2million additional RL steps**. All exactly inherit the same paired supervised student and train-only standardizer. Critic/optimizer start fresh and matched. Gate, plant, observer, action grid and20 observed actor inputs remain frozen.

Anchor coefficient1 KL(student||actor) uses half current rollout observations and half existing Step2 TRAIN-observation replay; no new labels. Credit uses a training-only single-request200ms zero-innovation counterfactual through the actual worker/gate, and excludes ignored in-flight actions from actor/entropy gradients. It is model-predicted credit, not the actual future outcome.

Checkpoint choice uses2,052 development episodes and is frozen before1,188 fresh final episodes. Selected and100k endpoint results remain separate. Exact step0 retention is not a PPO gain.

| Method | Survived /108 | Penalized RMSE (m) | Seed mean SD | Reduction vs student | Reduction vs LQR |
|---|---:|---:|---:|---:|---:|
| lqr | 108 | 0.084318 | 0.000252 | -2.074% | +0.000% |
| fixed_m004 | 108 | 0.083672 | 0.000256 | -1.292% | +0.766% |
| student | 108 | 0.082605 | 0.000260 | +0.000% | +2.031% |
| plain_selected | 108 | 0.082605 | 0.000260 | +0.000% | +2.031% |
| anchor_selected | 108 | 0.082620 | 0.000238 | -0.017% | +2.014% |
| credit_selected | 108 | 0.082600 | 0.000260 | +0.007% | +2.038% |
| combined_selected | 108 | 0.082614 | 0.000249 | -0.011% | +2.021% |
| plain_100k | 108 | 0.083204 | 0.000658 | -0.725% | +1.321% |
| anchor_100k | 108 | 0.082597 | 0.000256 | +0.010% | +2.041% |
| credit_100k | 108 | 0.082632 | 0.000219 | -0.033% | +2.000% |
| combined_100k | 108 | 0.082595 | 0.000245 | +0.013% | +2.044% |

## Development-only selection

| Arm | RL seed | Selected steps | Eligible | DEV RMSE |
|---|---:|---:|---|---:|
| plain | 2701 | 0 | True | 0.082906 |
| anchor | 2701 | 0 | True | 0.082906 |
| credit | 2701 | 100000 | True | 0.082872 |
| combined | 2701 | 100000 | True | 0.082898 |
| plain | 2802 | 0 | True | 0.082825 |
| anchor | 2802 | 0 | True | 0.082825 |
| credit | 2802 | 0 | True | 0.082825 |
| combined | 2802 | 0 | True | 0.082825 |
| plain | 2903 | 0 | True | 0.082680 |
| anchor | 2903 | 25000 | True | 0.082678 |
| credit | 2903 | 0 | True | 0.082680 |
| combined | 2903 | 25000 | True | 0.082678 |

## Frozen success screens

| Check | plain | anchor | credit | combined |
|---|---|---|---|---|
| improves_student_by_1pct | False | False | False | False |
| improves_lqr_by_1pct | True | True | True | True |
| improves_fixed_by_1pct | True | True | True | True |
| all_seed_means_better_than_student | False | False | False | False |
| selections_eligible | True | True | True | True |
| regional_survival | True | True | True | True |
| nominal_preserved | True | True | True | True |
| other_active_regions_preserved | True | True | True | True |
| **All checks** | False | False | False | False |

## Regions: selected models

| Region | Student | Plain | Anchor | Credit | Combined |
|---|---:|---:|---:|---:|---:|
| nominal | 0.060309 | 0.060309 | 0.060309 | 0.060312 | 0.060305 |
| tire_mismatch | 0.172204 | 0.172204 | 0.172282 | 0.172173 | 0.172275 |
| low_friction | 0.079577 | 0.079577 | 0.079581 | 0.079575 | 0.079567 |
| sensor_stress | 0.060309 | 0.060309 | 0.060309 | 0.060303 | 0.060303 |
| latency20 | 0.060746 | 0.060746 | 0.060751 | 0.060749 | 0.060750 |
| latency100 | 0.062486 | 0.062486 | 0.062486 | 0.062486 | 0.062486 |

## Seed means: selected models

| RL seed | Student | Plain | Anchor | Credit | Combined |
|---|---:|---:|---:|---:|---:|
| 2701 | 0.082614 | 0.082614 | 0.082614 | 0.082598 | 0.082619 |
| 2802 | 0.082860 | 0.082860 | 0.082860 | 0.082860 | 0.082860 |
| 2903 | 0.082341 | 0.082341 | 0.082384 | 0.082341 | 0.082363 |

## Fixed100k endpoint factorial contrasts

Negative RMSE differences favor the named factor. These are paired descriptive contrasts; three seed/noise pairs do not support a general significance or unique-cause claim. The credit factor includes both reward replacement and ignored-action masking. Selection is not used for factorial attribution.

| RL seed | Anchor without credit (m) | Credit without anchor (m) | Interaction (m) |
|---|---:|---:|---:|
| 2701 | -0.000230 | -0.000240 | +0.000251 |
| 2802 | -0.001117 | -0.001097 | +0.001077 |
| 2903 | -0.000475 | -0.000379 | +0.000381 |

## Compute and limits

| Job | Wall seconds | Final Adam steps |
|---|---:|---:|
| plain-2701 | 62.9 | 4994 |
| anchor-2701 | 80.9 | 4953 |
| credit-2701 | 109.2 | 5000 |
| combined-2701 | 120.0 | 5000 |
| plain-2802 | 63.4 | 4979 |
| anchor-2802 | 86.7 | 5000 |
| credit-2802 | 130.9 | 5000 |
| combined-2802 | 109.4 | 5000 |
| plain-2903 | 93.0 | 4968 |
| anchor-2903 | 85.4 | 4998 |
| credit-2903 | 104.1 | 5000 |
| combined-2903 | 93.7 | 5000 |

Same RL-transition budget is not equal wall compute: replay KL and reward forecasting add overhead. Counterfactual forecasts use current privileged state/parameters and zero future innovations; they can be biased and are never inference inputs. No actual future-noise stream is used in rewards. Physical execution and actor features remain identical.

Known geometries/condition families with fresh noise only. All failures retained with2.5m tails. Latency100ms is exact LQR fallback. No independently strong MPC comparison, native timing, unseen-domain validation, stability/safety proof or production promotion. No extra seeds, coefficients, rewards or teacher data were tried after outcomes.
