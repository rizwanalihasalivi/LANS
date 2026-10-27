# Submitted-action credit training study

| Source | Tracking gain vs LQR | Heading change | Rate RMS change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.00% | +0.00% | 96/96 |
| negative | +1.151% | -3.30% | +3.36% | 96/96 |
| positive | +1.151% | -3.30% | +3.36% | 96/96 |
| student | +2.061% | -0.31% | +3.14% | 96/96 |
| v3ppo | +2.566% | -0.52% | +4.01% | 96/96 |
| all_actions | +2.371% | -0.59% | +4.46% | 96/96 |
| submitted_only | +2.611% | -0.51% | +4.51% | 96/96 |

Selected arm: None.

New interface causal_filter_history_v5 explicitly assigns14 to past filtered residual/0.08;15/16/17/19 remainzero. All original models are logit-preserving bridges with input14ignored. Same fixed supervisor, objective and extra training budget in both credit arms; actor losses differ only by submitted-action masking. Existing v3 training/pretraining are extra; no per-seed checkpoint/arm selection. Finite development success is not unseen or physical validation.
