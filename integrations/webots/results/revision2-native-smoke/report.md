# Frozen-gate native Webots transfer

Audited **3 native runs**, survived **3/3**. Frozen gate and all policy hashes verified; no retraining or retuning.

| Region | Method | Survived | Mean penalized RMSE (m) | Active ticks | Mean weight | Mean per-run p99 age (ms) |
|---|---|---:|---:|---:|---:|---:|
| nominal | lqr | 1/1 | 0.053527 | 0.00% | 0.0000 | 0.00 |
| nominal | gated_residual | 1/1 | 0.052648 | 5.15% | 0.0076 | 10.00 |
| nominal | gated_full | 1/1 | 0.051805 | 7.46% | 0.0105 | 10.00 |

## Scope and limits

DLC220 only; same five trained policy seeds, fresh native noise seeds. Every method shares each physical/sensor condition. The gate uses nominal state estimates, local curvature and measured wheel angle; it never receives changed contact parameters. Native force-dependent contact slip is not Fiala. Contact softening divides calibrated slip by 0.65; this is not a measured 35% corner-stiffness reduction.

Both learned controllers use a real separate inference process, one job in flight, drop while busy. Added 0/20/100 ms is a minimum simulation-clock availability delay, not a guarantee of actual age. Two native runs share the cloud CPU; timing and output schedules are not deterministically repeatable or real-time guarantees. Zero learned authority should give deterministic physical LQR behavior, which is checked directly.

The actuator keeps the existing explicit Euler 1 ms lag/rate implementation and native wheel-angle proxy; these differ slightly from surrogate RK4/virtual-angle sensing. Nominal mass/CG/inertia audits pass. Native warmup and zero initial path offset differ from the surrogate initial disturbance. Reported improvement is conditional on this tested grid, not broad generalization or safety/stability proof. All scenarios and both learned roles are reported without post-test selection or retuning.
