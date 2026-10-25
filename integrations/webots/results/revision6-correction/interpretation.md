# Interpretation and next decision

This is the outcome of the user-authorized correction-quality pilot, not a claim that the goal is solved. The [verified generated report](report.md), [raw development episodes](evaluation/episodes.csv), [frozen protocol](../../research/revision6/protocol.json), and [checkpoint verification](checkpoint-verification.json) retain the full evidence.

| Method | Mean penalized episode RMSE (m) | Reduction versus LQR |
|---|---:|---:|
| LQR | 0.084355701 | — |
| New nominal constrained MPC reference | 0.095833177 | −13.606% (worse) |
| Constant positive candidate + frozen gate | 0.083998752 | 0.423% |
| Constant negative candidate + frozen gate | 0.083718174 | 0.756% |
| Direct-trained PPO + frozen gate | 0.084375063 | −0.023% (worse) |
| Execution-trained PPO + frozen gate | 0.084248163 | 0.127% |

Execution-aware training reduces error by **0.1504% versus direct training**, with a better mean in all three seeds. The absolute mean difference is only about0.000127m, and the descriptive seed-level95% interval includes zero. It fails the predeclared1% material-improvement target. It is also **0.633% worse than the constant negative candidate**. There is no demonstrated learning-specific advantage and no basis for model promotion or an automatic larger training run.

Both training arms use the same executed-command reward, with a true-state/plant counterfactual term allowed only during training. Execution-trained actions earn positive mean relative reward, but useful authority remains sparse (2.3–3.1% of training ticks). Direct training has negative mean relative reward. These diagnostics are consistent with a difficult sparse-control learning problem; they do not independently prove which mechanism causes the weak final gain. Positive training reward alone is not success.

The execution-trained hybrid is **12.09% lower RMSE than the particular nominal constrained MPC implementation** in this fresh grid, with no MPC solver fallbacks in145,692 calls. This satisfies the separately declared comparison rule against that implementation. However, **LQR also outperforms this MPC**, so that result cannot be attributed to learning and is not evidence of general superiority over MPC. No MPC parameter was retuned after observing the outcome. This nominal reference uses the same preview samples and measured signals as PPO but is not a best-tuned nonlinear MPC benchmark.

All648 episodes completed. Each method contributes108 cases, with the same plant/noise condition paired across methods. At100ms, learned/constant candidates exactly fall back to LQR. No native simulator, reserved final tests, old-model replacement or full-budget continuation was performed.

**Decision: do not promote either new100k policy.** Retain the previously qualified frozen controller and all negative evidence. Stop at the frozen pilot endpoint. A later proposal should address why learned corrections underperform the predeclared fixed candidates, and test one new hypothesis with a new protocol; simply increasing steps or learned authority is not supported by this pilot. The current experiment has not established a better new AI correction policy.
