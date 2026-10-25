# Descriptive actor drift

All24,300 original Step2 DEV observations and their existing labels/costs; no new teacher data, optimization or selection. These are off-policy supervised diagnostics, not fresh closed-loop results or proof of a causal mechanism.

| Arm | RL seed | Steps | Argmax agreement with student | KL(student || PPO) | Episode mean teacher regret | Nonzero decisions |
|---|---|---:|---:|---:|---:|---:|
| plain | 2701 | 100000 | 85.90% | 0.186682 | 0.015459 | 32.11% |
| anchor | 2701 | 100000 | 99.19% | 0.001246 | 0.013403 | 38.77% |
| credit | 2701 | 100000 | 91.95% | 0.135714 | 0.013720 | 42.65% |
| combined | 2701 | 100000 | 99.01% | 0.001783 | 0.013640 | 38.88% |
| plain | 2802 | 100000 | 83.74% | 0.195974 | 0.018051 | 31.33% |
| anchor | 2802 | 100000 | 98.90% | 0.001631 | 0.013067 | 38.83% |
| credit | 2802 | 100000 | 91.38% | 0.104068 | 0.013811 | 41.95% |
| combined | 2802 | 100000 | 98.61% | 0.002536 | 0.013186 | 39.23% |
| plain | 2903 | 100000 | 83.66% | 0.245530 | 0.019149 | 27.59% |
| anchor | 2903 | 100000 | 99.15% | 0.000823 | 0.013363 | 37.83% |
| credit | 2903 | 100000 | 93.02% | 0.083916 | 0.015180 | 40.25% |
| combined | 2903 | 100000 | 98.63% | 0.003556 | 0.013566 | 38.44% |

PPO target KL is relative to each rollout policy, so it does not prevent cumulative drift from the initial student. Higher teacher regret indicates disagreement with this finite expected-cost teacher on these fixed observations; it is not independently a tracking or generalization claim. All four arms were frozen before training; no post-outcome anchor/reward retuning was run. This diagnostic is not used for selection.
