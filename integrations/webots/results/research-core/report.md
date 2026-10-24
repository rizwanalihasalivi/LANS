# Verified campaign results

Final training: **10,000,000 steps**, ten policies, five seeds per role.
Surrogate comparison: **810 episodes**; native Webots transfer: **45 cases**. Failed cases remain in the denominators.

## Paired surrogate results

| Method | Survived / 135 | Corridor-clean / 135 | Mean failure-penalized RMSE (m) | SD across five seed means (m) |
|---|---:|---:|---:|---:|
| lqr | 135 | 135 | 0.064036 | 0.000554 |
| ppo | 87 | 87 | 0.865228 | 0.077337 |
| residual | 135 | 135 | 0.074852 | 0.005114 |
| fusion | 134 | 134 | 0.092369 | 0.032511 |
| no_supervisor | 134 | 134 | 0.093493 | 0.032387 |
| fixed_weight | 89 | 89 | 0.819828 | 0.048960 |

Each seed contributes 27 conditions per method. SD is across five seed means, not correlated time steps. Failure-penalized RMSE assigns 2.5 m error to the unexecuted remainder after tracking termination; it is a predefined score, not measured post-failure motion. Corridor checking is an additional sampled, non-ISO footprint metric.

## Native Webots transfer

| Mode | Added minimum delay (ms) | Survived / 15 | Mean tracking RMSE (m) | Mean fallback occupancy |
|---|---:|---:|---:|---:|
| ppo | 0 | 15 | 0.089703 | — |
| fusion | 0 | 15 | 0.085323 | 2.022% |
| fusion | 100 | 15 | 0.076902 | 100.000% |

These transfer RMSEs are over executed samples; consult survival and per-case CSVs rather than treating a truncated failed trajectory as a successful low-error run. Timing is diagnostic under cloud CPU contention, not a real-time deadline guarantee.

## Corrected LQR in Webots

| Speed (m/s) | Noiseless RMSE (m) | Noisy RMSE (m) | Noisy + 10 ms sensor-delay RMSE (m) |
|---|---:|---:|---:|
| 15 | 0.006761 | 0.006521 | 0.005880 |
| 20 | 0.052314 | 0.052643 | 0.047975 |
| 25 | 0.149970 | 0.170611 | 0.167736 |

## Parameter and numerical checks

- Runtime composite audit: 1,650 kg, nominal CG 1.4 m from the rear axle, nominal yaw inertia 4,224 kg·m².
- Wheel-inclusive track/geometry and steering sign/units checked from the actual world and motion.

| Speed (m/s), positive steer | Effective front stiffness (N/rad) | Effective rear stiffness (N/rad) |
|---|---:|---:|
| 15 | 83182.4 | 75931.2 |
| 20 | 84426.3 | 75361.1 |
| 25 | 85101.4 | 75100.4 |

These are steady-state effective small-slip estimates from a native contact model, not Fiala identification or real-vehicle measurements.
- Fiala surrogate, 1 ms vs 0.5 ms maximum final-state difference: 3.99e-12 (mixed state units; see raw vector values).

| Webots step | Relative steady-curvature difference vs 1 ms | Final lateral-position difference (m) |
|---|---:|---:|
| 2 ms | 0.012277% | 0.001890 |
| 5 ms | 0.015012% | -0.000383 |
| 10 ms | 0.426694% | -0.072114 |

## Course feasibility

| Smoothed course | Peak curvature (1/m) | Lateral acceleration at 15 / 20 / 25 m/s (m/s²) | Passes 0.8 μg margin |
|---|---:|---|---|
| candidate125 | 0.031715 | 7.136 / 12.686 / 19.822 | False / False / False |
| development220 | 0.005593 | 1.259 / 2.237 / 3.496 | True / True / True |

The 125 m result applies to the tested quintic smoothing of the proposed section lengths; it is not a statement about every possible 125 m path. The 220 m course is explicitly a different development geometry, with no ISO claim.

## Limits

- Held-out noise realizations, not unseen path geometries. Five seeds and these conditions do not establish general superiority or convergence.
- Native Webots contact slip is small-slip calibrated but is not the surrogate Fiala tire law; large-angle/load-transfer equivalence is unvalidated.
- PPO uses curvature previews; the analytical LQR uses local curvature. These are end-to-end comparisons, not a preview-information-matched learning ablation.
- Surrogate delays are deterministic service-time simulations; only native fusion uses a real separate inference process. Wall and simulation clocks are not interchangeable.
- Primary repository models, phase-1 experiments and specification remain unchanged. No real-vehicle safety or stability claim is made.
