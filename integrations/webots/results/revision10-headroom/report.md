# Longer-preview / action-sequence development diagnostic

Frozen design: `dcf203c`. Seventy-two new closed-loop episodes: one known DLC path at25m/s, six conditions, two paired development noise repetitions, six methods. No training, gate/actuator changes or final-test reuse.

All proposal policies are queried at most every50ms when the simulated worker accepts a request; held proposals are submitted between queries. This differs from the original revision8 teacher/student call cadence. The current student is remeasured here, not copied from its final evaluation. Teacher has privileged current state/parameters and known future geometry, but forecasts do not use actual future measurement noise.

| Method | Survival /12 | Mean penalized RMSE (m) | Reduction vs paired LQR |
|---|---:|---:|---:|
| lqr | 12 | 0.101342 | +0.000% |
| fixed_m004 | 12 | 0.100851 | +0.484% |
| student | 12 | 0.100842 | +0.493% |
| hold20 | 12 | 0.101111 | +0.228% |
| hold40 | 12 | 0.100698 | +0.635% |
| sequence40 | 12 | 0.100699 | +0.634% |

| Region | Student reduction | Hold200ms reduction | Hold400ms reduction | Sequence400ms reduction |
|---|---:|---:|---:|---:|
| nominal | +0.910% | +0.936% | +0.957% | +0.958% |
| tire_mismatch | -0.732% | -1.356% | -0.708% | -0.709% |
| low_friction | +1.524% | +1.130% | +1.728% | +1.727% |
| sensor_stress | +1.747% | +1.885% | +2.501% | +2.493% |
| latency20 | +1.179% | +1.072% | +1.232% | +1.232% |
| latency100 | +0.000% | +0.000% | +0.000% | +0.000% |

## Interpretation

The sequence method is a beam approximation: rank first actions by40-tick held cost, retain two, enumerate five second actions after20ticks, execute only the selected first action and replan. It is not exhaustive, an optimum or a controller ceiling. A longer surrogate horizon can improve predicted branch cost yet worsen closed-loop tracking.
These measurements support only this narrow development slice. Report all outcomes without choosing a design from final evaluation. Do not infer5% broad improvement, learned performance, unseen-domain generalization, native timing or safety. Severe100ms equality is fallback. No additional search/training/promotion follows this diagnostic.
