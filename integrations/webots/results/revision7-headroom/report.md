# Step1: finite-grid privileged oracle headroom

Five proposed residuals: −0.08/−0.04/0/+0.04/+0.08rad.200ms hold-candidate lookahead, recomputed on every available submission; actual gate, delayed packets, observer and actuator evolve in each cloned branch. Only one real10ms transition is applied after selection.

**This is not an absolute/theoretical performance ceiling.** It is one finite-action, finite-horizon receding policy, with true model/state and future sensor-noise privilege. It can be worse than a fixed policy over a whole episode; its minimum window cost does not establish global minimum RMSE or student learnability.

| Method | Survived /108 | Mean penalized episode RMSE (m) | Noise-seed mean SD | Reduction vs LQR |
|---|---:|---:|---:|---:|
| lqr | 108 | 0.084356 | 0.000127 | +0.000% |
| fixed_m008 | 108 | 0.083718 | 0.000108 | +0.756% |
| fixed_m004 | 108 | 0.083664 | 0.000168 | +0.820% |
| fixed_zero | 108 | 0.084356 | 0.000127 | +0.000% |
| fixed_p004 | 108 | 0.084058 | 0.000195 | +0.352% |
| fixed_p008 | 108 | 0.083999 | 0.000121 | +0.423% |
| oracle_gated | 108 | 0.082605 | 0.000137 | +2.076% |
| oracle_bypass | 18 | 1.852602 | 0.000983 | -2096.178% |

Best global fixed proposal on these development data: **fixed_m004**. This is a descriptive baseline selection, not an untouched-test win. All five fixed candidates remain reported.

| Region | LQR | Best fixed | Gated oracle | Bypass oracle | Gated reduction vs LQR |
|---|---:|---:|---:|---:|---:|
| nominal | 0.062578 | 0.061548 | 0.060197 | 2.231244 | +3.806% |
| tire_mismatch | 0.175447 | 0.174405 | 0.173170 | 2.177613 | +1.298% |
| low_friction | 0.081091 | 0.080331 | 0.079223 | 2.182044 | +2.304% |
| sensor_stress | 0.061213 | 0.060765 | 0.059415 | 2.233884 | +2.938% |
| latency20 | 0.062768 | 0.061898 | 0.060587 | 2.227789 | +3.475% |
| latency100 | 0.063036 | 0.063036 | 0.063036 | 0.063036 | +0.000% |

| Noise seed | LQR | Gated oracle | Bypass oracle | Gated reduction vs LQR |
|---|---:|---:|---:|---:|
| 301 | 0.084225 | 0.082448 | 1.852979 | +2.111% |
| 402 | 0.084363 | 0.082664 | 1.851486 | +2.013% |
| 503 | 0.084479 | 0.082702 | 1.853340 | +2.103% |

## Frozen diagnostic spending screen

| Check | Passed |
|---|---|
| gain_vs_lqr_at_least_1pct | True |
| gain_vs_best_global_fixed_at_least_1pct | True |
| all_noise_seed_means_better_than_lqr | True |
| regional_survival_preserved | True |
| no_active_region_over_1pct_worse | True |

Promising finite diagnostic: **True**. Neither a pass nor a fail proves a theoretical ceiling, a tight gate, student learnability or safety. No Step2/training or gate deployment change is launched.

## Verification and limits

324 stored reference cells (LQR and both±.08 constants) match revision6 within1e-10m; maximum difference 6.38e-16m. Checked 140,511 selected minima in 199,179 oracle trajectory rows. All five branch costs and selected proposals are retained. Zero proposal equals LQR; every100ms stale case exactly falls back.

Three noise repetitions, three speeds, two known paths, six regions,864 paired episodes. Noise IDs intentionally reuse development cells to verify parity. No new learned model, reserved data, native simulator or physical vehicle evidence. Primary metric is full-episode error with2.5m failed-tail fill; lookahead uses cumulative lateral error only. Window cost can trade heading/control behavior against short-term lateral error, so it is not a globally optimal controller.

Bypass is an evaluation-only combined removal of performance/envelope/persistence/weight restrictions, with unchanged proposal/physical limits and stale fallback. It cannot isolate one threshold, and its authority is not enabled in production. Gate-based branches still use only estimated state/measured speed; hidden physical parameters and future noise are used by the privileged selector, not the gate.

PPO receives tracking/survival rewards on every tick. Sparse accepted corrections mean sparse action-dependent feedback, not an absence of all reward. A later teacher/student protocol must remove or explicitly study future-noise privilege; this diagnostic is not ready-to-use supervision.
