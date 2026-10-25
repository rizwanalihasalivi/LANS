# Longer-preview / action-sequence development diagnostic

Corrected executable freeze: `0e4848a38a08c6d1b69b33a675427c068243957a`. Seventy-two new closed-loop episodes: one known DLC path at25m/s, six conditions, two paired development noise repetitions, six methods. No training, gate/actuator changes or final-test reuse.

All proposal policies are queried at most every50ms when the simulated worker accepts a request; between queries existing packets retain their original observation timestamp. Prediction branches use the same50ms submission cadence. This differs from the original revision8 teacher/student call cadence. The current student is remeasured here, not copied from its final evaluation. Teacher has privileged current state/parameters and known future geometry, but forecasts do not use actual future measurement noise.

| Method | Survival /12 | Mean penalized RMSE (m) | Reduction vs paired LQR |
|---|---:|---:|---:|
| lqr | 12 | 0.101342 | +0.000% |
| fixed_m004 | 12 | 0.100952 | +0.384% |
| student | 12 | 0.100906 | +0.430% |
| hold20 | 12 | 0.101155 | +0.184% |
| hold40 | 12 | 0.100864 | +0.471% |
| sequence40 | 12 | 0.100864 | +0.471% |

| Region | Student reduction | Hold200ms reduction | Hold400ms reduction | Sequence400ms reduction |
|---|---:|---:|---:|---:|
| nominal | +0.878% | +1.090% | +0.920% | +0.921% |
| tire_mismatch | -0.302% | -1.103% | -0.642% | -0.642% |
| low_friction | +1.261% | +1.090% | +1.633% | +1.633% |
| sensor_stress | +1.656% | +1.736% | +2.292% | +2.292% |
| latency20 | +0.075% | +0.133% | +0.149% | +0.149% |
| latency100 | +0.000% | +0.000% | +0.000% | +0.000% |

## Interpretation

The sequence method is a beam approximation: rank first actions by40-tick held cost, retain two, enumerate five second actions after20ticks, execute only the selected first action and replan. It is not exhaustive, an optimum or a controller ceiling. A longer surrogate horizon can improve predicted branch cost yet worsen closed-loop tracking.
These measurements support only this narrow development slice. Report all outcomes without choosing a design from final evaluation. Do not infer5% broad improvement, learned performance, unseen-domain generalization, native timing or safety. Severe100ms equality is fallback. No additional search/training/promotion follows this diagnostic.
