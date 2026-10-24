# Controller review remediation diagnostics

Corrected diagnostic freeze: `b86cfa8` (initial entry point `e058786` omitted the frozen LQR loader; that invalid run is retained separately). These are development data, not new reserved tests or a training campaign. Historical sources and checkpoints remain unchanged.

## Paired nonlearned controls

| Method | Survival /72 | Mean penalized RMSE (m) | Change vs LQR |
|---|---:|---:|---:|
| lqr | 72 | 0.084253 | +0.000% |
| legacy | 72 | 0.082702 | -1.841% |
| A100k | 72 | 0.083821 | -0.514% |
| zero | 72 | 0.084253 | +0.000% |
| constant_positive | 72 | 0.083757 | -0.589% |
| constant_negative | 72 | 0.083614 | -0.759% |
| linear_correction | 72 | 0.084253 | +0.000% |

| Region | Method | RMSE (m) | Seed101 change vs LQR | Seed202 change vs LQR |
|---|---|---:|---:|---:|
| nominal | lqr | 0.063117 | +0.000% | +0.000% |
| nominal | legacy | 0.061223 | -2.797% | -3.205% |
| nominal | A100k | 0.062454 | -0.634% | -1.467% |
| nominal | zero | 0.063117 | +0.000% | +0.000% |
| nominal | constant_positive | 0.062441 | -1.154% | -0.991% |
| nominal | constant_negative | 0.062130 | -1.683% | -1.448% |
| nominal | linear_correction | 0.063117 | +0.000% | +0.000% |
| tire_mismatch | lqr | 0.174511 | +0.000% | +0.000% |
| tire_mismatch | legacy | 0.172033 | -1.236% | -1.605% |
| tire_mismatch | A100k | 0.173859 | -0.279% | -0.469% |
| tire_mismatch | zero | 0.174511 | +0.000% | +0.000% |
| tire_mismatch | constant_positive | 0.173568 | -0.515% | -0.566% |
| tire_mismatch | constant_negative | 0.173246 | -0.736% | -0.713% |
| tire_mismatch | linear_correction | 0.174511 | +0.000% | +0.000% |
| low_friction | lqr | 0.081536 | +0.000% | +0.000% |
| low_friction | legacy | 0.080137 | -1.604% | -1.829% |
| low_friction | A100k | 0.081123 | -0.284% | -0.731% |
| low_friction | zero | 0.081536 | +0.000% | +0.000% |
| low_friction | constant_positive | 0.081115 | -0.426% | -0.608% |
| low_friction | constant_negative | 0.080866 | -0.882% | -0.760% |
| low_friction | linear_correction | 0.081536 | +0.000% | +0.000% |
| sensor_stress | lqr | 0.060837 | +0.000% | +0.000% |
| sensor_stress | legacy | 0.059207 | -2.087% | -3.262% |
| sensor_stress | A100k | 0.060656 | +0.324% | -0.911% |
| sensor_stress | zero | 0.060837 | +0.000% | +0.000% |
| sensor_stress | constant_positive | 0.060493 | -0.372% | -0.755% |
| sensor_stress | constant_negative | 0.060801 | +0.095% | -0.211% |
| sensor_stress | linear_correction | 0.060837 | +0.000% | +0.000% |
| latency20 | lqr | 0.062873 | +0.000% | +0.000% |
| latency20 | legacy | 0.060969 | -2.811% | -3.245% |
| latency20 | A100k | 0.062185 | -0.703% | -1.483% |
| latency20 | zero | 0.062873 | +0.000% | +0.000% |
| latency20 | constant_positive | 0.062280 | -1.129% | -0.760% |
| latency20 | constant_negative | 0.061995 | -1.369% | -1.425% |
| latency20 | linear_correction | 0.062873 | +0.000% | +0.000% |
| latency100 | lqr | 0.062646 | +0.000% | +0.000% |
| latency100 | legacy | 0.062646 | +0.000% | +0.000% |
| latency100 | A100k | 0.062646 | +0.000% | +0.000% |
| latency100 | zero | 0.062646 | +0.000% | +0.000% |
| latency100 | constant_positive | 0.062646 | +0.000% | +0.000% |
| latency100 | constant_negative | 0.062646 | +0.000% | +0.000% |
| latency100 | linear_correction | 0.062646 | +0.000% | +0.000% |

## Predictor audit

The table counts shadow-gate decisions on common LQR trajectories. These are correlated sampled states, not independent trials or deployed hybrid trajectories. `False reject` means a cost rejection while at least one currently ramp-allowed blend has >1% realized cost benefit. Age/envelope/persistence exclusions are counted separately. `False accept` requires >1% realized harm; small changes are neutral.

| Method | Sampled states | Accepted | False accepts / accepted | Cost rejects | False rejects / cost rejects | Helpful withheld by safety/recovery |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 2608 | 664 | 38/664 | 1893 | 98/1893 | 23 |
| A100k | 2608 | 451 | 77/451 | 2112 | 117/2112 | 22 |
| zero | 2608 | 0 | 0/0 | 2608 | 0/2608 | 0 |
| constant_positive | 2608 | 655 | 128/655 | 1884 | 114/1884 | 32 |
| constant_negative | 2608 | 621 | 117/621 | 1920 | 146/1920 | 31 |
| linear_correction | 2608 | 0 | 0/0 | 2608 | 0/2608 | 0 |

| Region | Proposal comparisons | Estimated-state delta MAE | True-state predictor delta MAE |
|---|---:|---:|---:|
| nominal | 11736 | 8.4493016e-06 | 4.6255745e-06 |
| tire_mismatch | 11736 | 2.2761131e-05 | 2.8436847e-05 |
| low_friction | 11736 | 9.9200764e-06 | 7.131852e-06 |
| sensor_stress | 11736 | 1.3006193e-05 | 5.420634e-06 |

## Interpretation limits

All fixed signs, zero and a predeclared linear correction are retained. Nonlearned controls use only the same observable errors. A learning-specific benefit requires beating these controls on independent evidence; lower error than LQR alone does not establish that benefit.
The realized cost branches use privileged true-state continuation and actual plant parameters only inside offline diagnostics. Predictor uses nominal linear physics and local curvature; realized branches use nonlinear dynamics, evolving geometry and actuator lag. True-state predictor columns help separate estimation effects from model/geometry mismatch but are not deployed alternatives. No hidden parameters are passed to the frozen gate.
Legacy PPO is a 1M-step model; A is 100k and uses different seed mapping. Their budgets are not matched. The same known development grid is reused deliberately for attribution, not claimed as fresh generalization. The 5% research target remains unmet unless separately demonstrated; these diagnostics do not authorize full training.
No gate settings were tuned, no standalone policy was relabeled as residual, no research policy was trained and no native Webots or final reserved campaign was run. Severe-delay equality is fallback, not a learned win. Small corrected-root and execution-interface smoke models elsewhere are not performance evidence.
