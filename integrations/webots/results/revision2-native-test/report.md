# Frozen-gate native Webots transfer

Audited **270 native runs**, survived **270/270**. Frozen gate and all policy hashes verified; no retraining or retuning.

| Region | Method | Survived | Mean penalized RMSE (m) | Active ticks | Mean weight | Mean per-run p99 age (ms) |
|---|---|---:|---:|---:|---:|---:|
| nominal | lqr | 15/15 | 0.077213 | 0.00% | 0.0000 | 0.00 |
| nominal | gated_residual | 15/15 | 0.076216 | 7.02% | 0.0127 | 14.67 |
| nominal | gated_full | 15/15 | 0.076760 | 9.23% | 0.0144 | 16.70 |
| contact_softening | lqr | 15/15 | 0.166475 | 0.00% | 0.0000 | 0.00 |
| contact_softening | gated_residual | 15/15 | 0.166120 | 4.21% | 0.0073 | 12.41 |
| contact_softening | gated_full | 15/15 | 0.166808 | 6.69% | 0.0101 | 13.33 |
| low_friction | lqr | 15/15 | 0.087617 | 0.00% | 0.0000 | 0.00 |
| low_friction | gated_residual | 15/15 | 0.086465 | 7.58% | 0.0146 | 16.00 |
| low_friction | gated_full | 15/15 | 0.086484 | 9.08% | 0.0145 | 20.03 |
| sensor_stress | lqr | 15/15 | 0.073189 | 0.00% | 0.0000 | 0.00 |
| sensor_stress | gated_residual | 15/15 | 0.072478 | 8.35% | 0.0173 | 14.01 |
| sensor_stress | gated_full | 15/15 | 0.073440 | 12.33% | 0.0237 | 23.71 |
| latency20 | lqr | 15/15 | 0.077760 | 0.00% | 0.0000 | 0.00 |
| latency20 | gated_residual | 15/15 | 0.077049 | 7.04% | 0.0111 | 30.67 |
| latency20 | gated_full | 15/15 | 0.077289 | 9.51% | 0.0134 | 32.67 |
| latency100 | lqr | 15/15 | 0.077577 | 0.00% | 0.0000 | 0.00 |
| latency100 | gated_residual | 15/15 | 0.077577 | 0.00% | 0.0000 | 190.00 |
| latency100 | gated_full | 15/15 | 0.077577 | 0.00% | 0.0000 | 190.00 |

## Paired comparisons

Each paired seed mean aggregates the three speeds. Intervals are descriptive t(4) 95% intervals across five seed differences; no multiplicity-adjusted significance claim. Residual is primary; full-command is a predefined secondary comparison.

| Region | Hybrid | RMSE change | Paired difference (m) | 95% interval (m) | Better seeds / 5 | Survival delta | Clear ≥5% advantage |
|---|---|---:|---:|---|---:|---:|---|
| nominal | gated_residual | -1.29% | -0.000997 | [-0.001683, -0.000312] | 5 | +0 | False |
| nominal | gated_full | -0.59% | -0.000453 | [-0.001872, +0.000966] | 4 | +0 | False |
| contact_softening | gated_residual | -0.21% | -0.000355 | [-0.000549, -0.000162] | 5 | +0 | False |
| contact_softening | gated_full | +0.20% | +0.000332 | [-0.000615, +0.001280] | 2 | +0 | False |
| low_friction | gated_residual | -1.31% | -0.001152 | [-0.001459, -0.000844] | 5 | +0 | False |
| low_friction | gated_full | -1.29% | -0.001133 | [-0.002148, -0.000118] | 4 | +0 | False |
| sensor_stress | gated_residual | -0.97% | -0.000710 | [-0.001255, -0.000166] | 5 | +0 | False |
| sensor_stress | gated_full | +0.34% | +0.000251 | [-0.001616, +0.002119] | 3 | +0 | False |
| latency20 | gated_residual | -0.91% | -0.000711 | [-0.001076, -0.000345] | 5 | +0 | False |
| latency20 | gated_full | -0.61% | -0.000471 | [-0.001917, +0.000975] | 4 | +0 | False |
| latency100 | gated_residual | +0.00% | +0.000000 | [+0.000000, +0.000000] | 0 | +0 | False |
| latency100 | gated_full | +0.00% | +0.000000 | [+0.000000, +0.000000] | 0 | +0 | False |

Severe-delay paired physical/control trajectories exactly equal LQR: **30/30**. Zero learned weight and local command equality verified for every severe-delay tick. Per-field maximum differences are retained in `verification.json`; exact means numerical equality, not a tolerance.

## Scope and limits

DLC220 only; same five trained policy seeds, fresh native noise seeds. Every method shares each physical/sensor condition. The gate uses nominal state estimates, local curvature and measured wheel angle; it never receives changed contact parameters. Native force-dependent contact slip is not Fiala. Contact softening divides calibrated slip by 0.65; this is not a measured 35% corner-stiffness reduction.

Both learned controllers use a real separate inference process, one job in flight, drop while busy. Added 0/20/100 ms is a minimum simulation-clock availability delay, not a guarantee of actual age. Two native runs share the cloud CPU; timing and output schedules are not deterministically repeatable or real-time guarantees. Zero learned authority should give deterministic physical LQR behavior, which is checked directly.

The actuator keeps the existing explicit Euler 1 ms lag/rate implementation and native wheel-angle proxy; these differ slightly from surrogate RK4/virtual-angle sensing. Nominal mass/CG/inertia audits pass. Native warmup and zero initial path offset differ from the surrogate initial disturbance. Reported improvement is conditional on this tested grid, not broad generalization or safety/stability proof. All scenarios and both learned roles are reported without post-test selection or retuning.
