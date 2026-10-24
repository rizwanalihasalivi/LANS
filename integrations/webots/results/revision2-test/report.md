# Performance-gated revision: reserved test results

Verified 900 paired episodes. Reused frozen policies: five trained seeds; new reserved noise streams. Development selected `{'horizon_steps': 20, 'relative_margin': 0.01}`; acceptance constraints passed: **True**.

No training or gate tuning used these reserved results. All predeclared regions and methods appear below. Confidence intervals are descriptive, unadjusted across six regions; they are not a multiple-comparison significance claim.

| Region | Method | Survived / 30 | Mean penalized RMSE (m) | Mean active fraction | Mean weight |
|---|---|---:|---:|---:|---:|
| nominal | lqr | 30 | 0.062320 | 0.00% | 0.0000 |
| nominal | old_fusion | 30 | 0.087308 | 99.23% | 0.6815 |
| nominal | residual | 30 | 0.087454 | 100.00% | 1.0000 |
| nominal | gated_residual | 30 | 0.060475 | 12.34% | 0.0354 |
| nominal | gated_full | 30 | 0.060260 | 11.80% | 0.0290 |
| tire_mismatch | lqr | 30 | 0.175013 | 0.00% | 0.0000 |
| tire_mismatch | old_fusion | 30 | 0.165827 | 99.23% | 0.6815 |
| tire_mismatch | residual | 30 | 0.173295 | 100.00% | 1.0000 |
| tire_mismatch | gated_residual | 30 | 0.172810 | 6.09% | 0.0133 |
| tire_mismatch | gated_full | 30 | 0.171761 | 7.97% | 0.0141 |
| low_friction | lqr | 30 | 0.080833 | 0.00% | 0.0000 |
| low_friction | old_fusion | 30 | 0.101710 | 99.23% | 0.6815 |
| low_friction | residual | 30 | 0.102275 | 100.00% | 1.0000 |
| low_friction | gated_residual | 30 | 0.079308 | 9.73% | 0.0267 |
| low_friction | gated_full | 30 | 0.078990 | 9.95% | 0.0238 |
| sensor_stress | lqr | 30 | 0.061571 | 0.00% | 0.0000 |
| sensor_stress | old_fusion | 30 | 0.089116 | 99.23% | 0.6815 |
| sensor_stress | residual | 30 | 0.090326 | 100.00% | 1.0000 |
| sensor_stress | gated_residual | 30 | 0.060332 | 10.92% | 0.0319 |
| sensor_stress | gated_full | 30 | 0.060140 | 11.06% | 0.0273 |
| latency20 | lqr | 30 | 0.062804 | 0.00% | 0.0000 |
| latency20 | old_fusion | 30 | 0.077693 | 99.01% | 0.3501 |
| latency20 | residual | 30 | 0.069102 | 99.85% | 0.3789 |
| latency20 | gated_residual | 30 | 0.061098 | 12.42% | 0.0258 |
| latency20 | gated_full | 30 | 0.060651 | 11.33% | 0.0202 |
| latency100 | lqr | 30 | 0.063067 | 0.00% | 0.0000 |
| latency100 | old_fusion | 30 | 0.063067 | 0.00% | 0.0000 |
| latency100 | residual | 30 | 0.062889 | 99.23% | 0.0022 |
| latency100 | gated_residual | 30 | 0.063067 | 0.00% | 0.0000 |
| latency100 | gated_full | 30 | 0.063067 | 0.00% | 0.0000 |

## Predeclared primary comparison: gated residual vs LQR

Each paired difference is aggregated over six conditions per trained seed before computing the mean, sample SD and t(4) interval. Negative differences favor the hybrid. The five policies are reused, not newly trained independent replicas.

| Region | RMSE change | Mean paired difference (m) | Seed SD (m) | Descriptive 95% interval (m) | Better seeds / 5 | Survival delta | Meets region criterion |
|---|---:|---:|---:|---|---:|---:|---|
| nominal | -2.96% | -0.001845 | 0.000232 | [-0.002134, -0.001557] | 5 | +0 | False |
| tire_mismatch | -1.26% | -0.002203 | 0.000418 | [-0.002722, -0.001685] | 5 | +0 | False |
| low_friction | -1.89% | -0.001525 | 0.000205 | [-0.001779, -0.001271] | 5 | +0 | False |
| sensor_stress | -2.01% | -0.001239 | 0.000329 | [-0.001648, -0.000830] | 5 | +0 | False |
| latency20 | -2.72% | -0.001705 | 0.000272 | [-0.002044, -0.001367] | 5 | +0 | False |
| latency100 | +0.00% | +0.000000 | 0.000000 | [+0.000000, +0.000000] | 0 | +0 | False |

Nominal preservation criterion (≤2% RMSE increase, no survival decrease): **True**.
Clear advantage regions (≥5% mean reduction, all five seed differences negative, no survival decrease): **none**.

At 100 ms, the gate rejects every learned packet and must reproduce paired LQR exactly. This is a fallback contract, not an advantage over LQR.

## Interpretation and limits

The gate is a nominal linear model prediction using the same noisy state estimate, known speed, current map curvature and actuator encoder. It never receives true lateral velocity, hidden tire stiffness, friction or future noise. A predicted cost decrease is not a guarantee of realized tracking improvement. Candidate control is held for 50 ms in the predictor, followed by LQR continuation; future learned actions are not predicted.

This is a new surrogate development revision, not native Webots transfer validation of the new gate. Previous native Webots evidence applies to the previous controller. Paths and learned policy seeds are reused; only the noise streams are new. Service-time delays are simulated, not actual concurrent inference. No hard-real-time, stability, safety or publishability claim follows. No test-driven weight adjustment was made.
