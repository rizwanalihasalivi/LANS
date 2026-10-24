# INVALID RUN — DO NOT USE AS PERFORMANCE EVIDENCE

The diagnostic entry point omitted the frozen LQR configuration. This report is retained only to disclose that error. See sibling `revision5-audit` for corrected results validated against historical reference rows.

# Controller review remediation diagnostics

Frozen diagnostic protocol: `e058786`. These are development data, not new reserved tests or a training campaign. Historical sources and checkpoints remain unchanged.

## Paired nonlearned controls

| Method | Survival /72 | Mean penalized RMSE (m) | Change vs LQR |
|---|---:|---:|---:|
| lqr | 0 | 2.273549 | +0.000% |
| legacy | 0 | 2.273549 | +0.000% |
| A100k | 0 | 2.273549 | +0.000% |
| zero | 0 | 2.273549 | +0.000% |
| constant_positive | 0 | 2.273549 | +0.000% |
| constant_negative | 0 | 2.273549 | +0.000% |
| linear_correction | 0 | 2.273549 | +0.000% |

| Region | Method | RMSE (m) | Seed101 change vs LQR | Seed202 change vs LQR |
|---|---|---:|---:|---:|
| nominal | lqr | 2.275229 | +0.000% | +0.000% |
| nominal | legacy | 2.275229 | +0.000% | +0.000% |
| nominal | A100k | 2.275229 | +0.000% | +0.000% |
| nominal | zero | 2.275229 | +0.000% | +0.000% |
| nominal | constant_positive | 2.275229 | +0.000% | +0.000% |
| nominal | constant_negative | 2.275229 | +0.000% | +0.000% |
| nominal | linear_correction | 2.275229 | +0.000% | +0.000% |
| tire_mismatch | lqr | 2.264001 | +0.000% | +0.000% |
| tire_mismatch | legacy | 2.264001 | +0.000% | +0.000% |
| tire_mismatch | A100k | 2.264001 | +0.000% | +0.000% |
| tire_mismatch | zero | 2.264001 | +0.000% | +0.000% |
| tire_mismatch | constant_positive | 2.264001 | +0.000% | +0.000% |
| tire_mismatch | constant_negative | 2.264001 | +0.000% | +0.000% |
| tire_mismatch | linear_correction | 2.264001 | +0.000% | +0.000% |
| low_friction | lqr | 2.260095 | +0.000% | +0.000% |
| low_friction | legacy | 2.260095 | +0.000% | +0.000% |
| low_friction | A100k | 2.260095 | +0.000% | +0.000% |
| low_friction | zero | 2.260095 | +0.000% | +0.000% |
| low_friction | constant_positive | 2.260095 | +0.000% | +0.000% |
| low_friction | constant_negative | 2.260095 | +0.000% | +0.000% |
| low_friction | linear_correction | 2.260095 | +0.000% | +0.000% |
| sensor_stress | lqr | 2.283595 | +0.000% | +0.000% |
| sensor_stress | legacy | 2.283595 | +0.000% | +0.000% |
| sensor_stress | A100k | 2.283595 | +0.000% | +0.000% |
| sensor_stress | zero | 2.283595 | +0.000% | +0.000% |
| sensor_stress | constant_positive | 2.283595 | +0.000% | +0.000% |
| sensor_stress | constant_negative | 2.283595 | +0.000% | +0.000% |
| sensor_stress | linear_correction | 2.283595 | +0.000% | +0.000% |
| latency20 | lqr | 2.280278 | +0.000% | +0.000% |
| latency20 | legacy | 2.280278 | +0.000% | +0.000% |
| latency20 | A100k | 2.280278 | +0.000% | +0.000% |
| latency20 | zero | 2.280278 | +0.000% | +0.000% |
| latency20 | constant_positive | 2.280278 | +0.000% | +0.000% |
| latency20 | constant_negative | 2.280278 | +0.000% | +0.000% |
| latency20 | linear_correction | 2.280278 | +0.000% | +0.000% |
| latency100 | lqr | 2.278098 | +0.000% | +0.000% |
| latency100 | legacy | 2.278098 | +0.000% | +0.000% |
| latency100 | A100k | 2.278098 | +0.000% | +0.000% |
| latency100 | zero | 2.278098 | +0.000% | +0.000% |
| latency100 | constant_positive | 2.278098 | +0.000% | +0.000% |
| latency100 | constant_negative | 2.278098 | +0.000% | +0.000% |
| latency100 | linear_correction | 2.278098 | +0.000% | +0.000% |

## Predictor audit

The table counts shadow-gate decisions on common LQR trajectories. These are correlated sampled states, not independent trials or deployed hybrid trajectories. `False reject` means a cost rejection while at least one currently ramp-allowed blend has >1% realized cost benefit. Age/envelope/persistence exclusions are counted separately. `False accept` requires >1% realized harm; small changes are neutral.

| Method | Sampled states | Accepted | False accepts / accepted | Cost rejects | False rejects / cost rejects | Helpful withheld by safety/recovery |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 513 | 0 | 0/0 | 403 | 0/403 | 0 |
| A100k | 513 | 0 | 0/0 | 403 | 0/403 | 0 |
| zero | 513 | 0 | 0/0 | 403 | 0/403 | 0 |
| constant_positive | 513 | 0 | 0/0 | 403 | 0/403 | 0 |
| constant_negative | 513 | 0 | 0/0 | 403 | 0/403 | 0 |
| linear_correction | 513 | 0 | 0/0 | 403 | 0/403 | 0 |

| Region | Proposal comparisons | Estimated-state delta MAE | True-state predictor delta MAE |
|---|---:|---:|---:|
| nominal | 2340 | 1.2178328e-05 | 7.5620872e-06 |
| tire_mismatch | 2340 | 1.0409576e-05 | 4.6284432e-06 |
| low_friction | 2358 | 4.6653472e-06 | 3.2905676e-06 |
| sensor_stress | 2196 | 4.5278926e-06 | 3.8061816e-06 |

## Interpretation limits

All fixed signs, zero and a predeclared linear correction are retained. Nonlearned controls use only the same observable errors. A learning-specific benefit requires beating these controls on independent evidence; lower error than LQR alone does not establish that benefit.
The realized cost branches use privileged true-state continuation and actual plant parameters only inside offline diagnostics. Predictor uses nominal linear physics and local curvature; realized branches use nonlinear dynamics, evolving geometry and actuator lag. True-state predictor columns help separate estimation effects from model/geometry mismatch but are not deployed alternatives. No hidden parameters are passed to the frozen gate.
Legacy PPO is a 1M-step model; A is 100k and uses different seed mapping. Their budgets are not matched. The same known development grid is reused deliberately for attribution, not claimed as fresh generalization. The 5% research target remains unmet unless separately demonstrated; these diagnostics do not authorize full training.
No gate settings were tuned, no standalone policy was relabeled as residual, no research policy was trained and no native Webots or final reserved campaign was run. Severe-delay equality is fallback, not a learned win. Small corrected-root and execution-interface smoke models elsewhere are not performance evidence.
