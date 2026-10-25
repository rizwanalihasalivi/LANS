# Descriptive actor drift

All24,300 original Step2 DEV observations and their existing labels/costs; no new teacher data, optimization or selection. These are off-policy supervised diagnostics, not fresh closed-loop results or proof of a causal mechanism.

| RL seed | Steps | Argmax agreement with student | KL(student || PPO) | Episode mean teacher regret | Nonzero decisions |
|---|---:|---:|---:|---:|---:|
| 1701 | 0 | 100.00% | 0.000000 | 0.013349 | 38.81% |
| 1701 | 25000 | 95.37% | 0.035691 | 0.013884 | 38.75% |
| 1701 | 50000 | 93.50% | 0.061986 | 0.014687 | 36.37% |
| 1701 | 100000 | 92.01% | 0.093234 | 0.014537 | 34.23% |
| 1802 | 0 | 100.00% | 0.000000 | 0.012963 | 38.92% |
| 1802 | 25000 | 94.87% | 0.032162 | 0.013750 | 39.51% |
| 1802 | 50000 | 88.87% | 0.070906 | 0.014492 | 37.75% |
| 1802 | 100000 | 82.14% | 0.157184 | 0.015825 | 37.60% |
| 1903 | 0 | 100.00% | 0.000000 | 0.013297 | 37.86% |
| 1903 | 25000 | 91.33% | 0.065540 | 0.014538 | 34.30% |
| 1903 | 50000 | 87.89% | 0.118616 | 0.015581 | 33.27% |
| 1903 | 100000 | 82.82% | 0.237841 | 0.018447 | 29.21% |

PPO target KL is relative to each rollout policy, so it does not prevent cumulative drift from the initial student. Higher teacher regret indicates disagreement with this finite expected-cost teacher on these fixed observations; it is not independently a tracking or generalization claim. No post-outcome teacher anchor or reward retuning was run.
