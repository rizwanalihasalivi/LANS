# Causal residual campaign: development

All metrics below are simulated-service closed-loop measurements, not native or real-time guarantees. PPO has 25,000 additional steps per seed; supervised pretraining is extra.

| Method | Penalized lateral RMSE (m) | Gain vs LQR | Heading RMSE (rad) | Steering-rate RMS (rad/s) | Survival |
|---|---:|---:|---:|---:|---:|
| lqr | 0.090578 | 0.000% | 0.020024 | 0.069169 | 96/96 |
| fixed_negative | 0.093213 | -2.909% | 0.020279 | 0.069490 | 96/96 |
| fixed_positive | 0.093213 | -2.909% | 0.020279 | 0.069490 | 96/96 |
| student | 0.090599 | -0.024% | 0.020027 | 0.069213 | 96/96 |
| scratch | 0.092441 | -2.057% | 0.020218 | 0.069551 | 96/96 |
| finetune | 0.090618 | -0.044% | 0.020029 | 0.069243 | 96/96 |
| fixed_authority | 0.099658 | -10.024% | 0.022049 | 0.147717 | 95/96 |
| latency_gain | 0.085469 | 5.640% | 0.020310 | 0.120488 | 96/96 |
| no_recovery | 0.090637 | -0.066% | 0.020032 | 0.069265 | 96/96 |

## Decision

Eligible: **False**.
- finetune lacks >=1% improvement vs lqr
- finetune lacks >=1% improvement vs student
- pair0 does not improve student
- pair1 does not improve student
- pair2 does not improve student

Independent raw-trace audit: 864 episodes, 192 exact severe-delay LQR pairs.

The latency-gain arm is a documented manuscript-inspired reconstruction, not an exact reproduction of a published algorithm. All simple-gain arms share stale rejection. No unknown future output or configured service delay enters the actor.

No formal neuro-symbolic novelty, published-controller superiority, hard-real-time, GPU speedup, energy, or vehicle-readiness claim is supported by this grid. If eligibility fails, reserved confirmation remains unopened.
