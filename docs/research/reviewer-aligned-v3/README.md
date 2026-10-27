# Execution-aligned predictive PPO development study

27 October2026. Frozen single supervisor/reward variant; old evidence unchanged. No post-outcome tuning or reserved evaluation.

| Source | Tracking gain vs LQR | Heading change | Actuator-rate change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.00% | +0.00% | 96/96 |
| negative | +0.653% | -2.28% | +2.22% | 96/96 |
| positive | +0.653% | -2.28% | +2.22% | 96/96 |
| student | +1.117% | -0.14% | +2.03% | 96/96 |
| oldppo | +1.151% | -0.16% | +2.05% | 96/96 |
| ppo | +1.445% | -0.27% | +2.66% | 96/96 |

Eligible: False. Reasons: lacks1% gain vs student; lacks1% gain vs negative; lacks1% gain vs positive

All methods share the new supervisor, actuator, observer and causal20-channel contract. Student is original supervised initialization, oldppo is the old25k endpoint, ppo is the new prespecified100k endpoint (or explicitly ineligible futility stop). Extra supervised pretraining is disclosed. Training reward measures actual actuator rate. The1s predictor assumes repeated proposals under healthy worker service for performance estimation; no future completion oracle enters the policy, and this is not a safety certificate.

Three training/noise pairs are small-sample development evidence; control ticks are not independent experiments. Physical readiness and hard real-time execution require separate evidence. No failed test is relabeled as a pass.
