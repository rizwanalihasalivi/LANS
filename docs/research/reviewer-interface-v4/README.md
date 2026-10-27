# Freshness-interface and scalar-predictor development study

27 October2026. Frozen single freshness variant; no training; old evidence unchanged. No post-outcome tuning or reserved evaluation.

| Source | Tracking gain vs LQR | Heading change | Actuator-rate change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.00% | +0.00% | 96/96 |
| negative | +0.998% | -3.29% | +3.42% | 96/96 |
| positive | +0.998% | -3.29% | +3.42% | 96/96 |
| student | +2.017% | -0.30% | +3.11% | 96/96 |
| oldage_ppo | +0.126% | -0.05% | +0.00% | 96/96 |
| ppo | +2.579% | -0.51% | +4.17% | 96/96 |
| planner | +2.450% | -6.28% | +4.43% | 96/96 |

Eligible: False. Reasons: lacks1% gain vs student

The same frozen v3 PPO endpoints and original students are used without training. oldage_ppo retains the legacy steep age-gain; other proposal methods share the new freshness-only authority. All cases enforce minimum10ms simulated delivery. Planner is a causal finite nominal nonlearned reference, not an optimal-policy or safety proof. All rewards/actuator/observer limits are unchanged.

Three training/noise pairs are small-sample development evidence; control ticks are not independent experiments. Physical readiness and hard real-time execution require separate evidence. No failed test is relabeled as a pass.
