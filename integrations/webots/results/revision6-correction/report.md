# Correction-quality pilot: fixed100k endpoints

Six policies from scratch, two arms × three seeds ×100k = **600,000 training steps**. Training protocol freeze `1201f8d`; evaluator/MPC freeze `55b8ff8`. No best-checkpoint selection, extensions or post-result tuning.

Both policies deploy through the same frozen gate. Direct means direct-residual **training**, not ungated deployment. Same20 observations, PPO settings, nominal training distribution and executed-command reward; service0 in both training arms. Only training execution changes.

## Paired development comparison

| Method | Survived /108 | Mean episode RMSE (m) | Seed-mean SD (m) | Change vs LQR |
|---|---:|---:|---:|---:|
| lqr | 108 | 0.084356 | 0.000127 | +0.000% |
| mpc | 108 | 0.095833 | 0.000211 | +13.606% |
| constant_positive | 108 | 0.083999 | 0.000121 | -0.423% |
| constant_negative | 108 | 0.083718 | 0.000108 | -0.756% |
| direct | 108 | 0.084375 | 0.000142 | +0.023% |
| execution | 108 | 0.084248 | 0.000248 | -0.127% |

Negative change means lower error. Equal weighting across episode/seed means; failure tails filled at2.5m. Different clocks and reused baseline calculations are not independent training replicas.

| Region | LQR | MPC | Constant + | Constant − | Direct-trained | Execution-trained |
|---|---:|---:|---:|---:|---:|---:|
| nominal | 0.062578 | 0.069718 | 0.061988 | 0.061616 | 0.062604 | 0.062512 |
| tire_mismatch | 0.175447 | 0.202774 | 0.174673 | 0.174440 | 0.175454 | 0.175169 |
| low_friction | 0.081091 | 0.089689 | 0.080611 | 0.080299 | 0.081129 | 0.080928 |
| sensor_stress | 0.061213 | 0.072333 | 0.061470 | 0.061042 | 0.061241 | 0.061187 |
| latency20 | 0.062768 | 0.070361 | 0.062215 | 0.061877 | 0.062786 | 0.062657 |
| latency100 | 0.063036 | 0.070125 | 0.063036 | 0.063036 | 0.063036 | 0.063036 |

## Paired training-effect uncertainty

| Seed | Direct-trained | Execution-trained | Difference (m) |
|---|---:|---:|---:|
| 301 | 0.084228 | 0.083986 | -0.000242 |
| 402 | 0.084386 | 0.084280 | -0.000106 |
| 503 | 0.084511 | 0.084479 | -0.000032 |

Descriptive t(2)95% interval for mean execution−direct difference: [-0.000391, +0.000138]m. Three seeds, no multiplicity correction or general-significance claim.

## Frozen operational criteria

### Primary training effect

| Check | Passed |
|---|---|
| improves_direct_by_1pct | False |
| at_least_two_seed_improvements | True |
| regional_survival | True |
| nominal_preserved | True |
| no_active_region_over_1pct_worse | True |
| severe_exact | True |

### Learning-specific benefit

| Check | Passed |
|---|---|
| beats_lqr_by_1pct | False |
| beats_positive_by_1pct | False |
| beats_negative_by_1pct | False |

### MPC comparison

| Check | Passed |
|---|---|
| improves_mpc_by_1pct | True |
| all_seed_improvements | True |
| regional_survival | True |

Primary progress: **False**. Learning benefit including primary checks: **False**. Declared MPC advantage: **True**.

## Training diagnostics

| Arm | Seed | Wall seconds | Gate active | Mean relative reward |
|---|---:|---:|---:|---:|
| direct | 301 | 58.33 | 100.00% | -0.000812 |
| direct | 402 | 79.37 | 100.00% | -0.003316 |
| direct | 503 | 56.31 | 100.00% | -0.000630 |
| execution | 301 | 57.07 | 3.09% | +0.000109 |
| execution | 402 | 78.56 | 2.43% | +0.000075 |
| execution | 503 | 55.73 | 2.30% | +0.000083 |

## MPC and scope limits

MPC calls: **145692**, solver/constraint fallbacks: **0**. Fallback uses the same local LQR and remains counted. This is a declared nominal linear/actuator constrained MPC, not an exhaustive optimal nonlinear MPC comparison.

Same noisy sensor/estimator, observed-speed channel, three curvature previews, nonlinear plant and physical constraints across learned/MPC methods. Local LQR uses its original current-curvature design. MPC re-plans locally; service0/20/100ms delays apply to learned/constant proposals, not an artificial delay imposed on local baselines. Wall solver/inference values are diagnostics under concurrent CPU load, not real-time guarantees.

Known sine120/DLC220 geometries and fresh development noise at three speeds/six regions. No final reserved noise, native Webots campaign, real-vehicle safety, stability or unseen-path claim. Training stays nominal and synchronous; tests under delayed/mismatched deployment do not claim those conditions were trained. The 600k budget is a pilot, not convergence proof.

**Stop at the predeclared pilot endpoint.** No automatic full training, new reward, gate change, arm selection or extra budget is authorized by this report.
