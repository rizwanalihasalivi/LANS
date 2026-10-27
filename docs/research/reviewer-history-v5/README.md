# Versioned causal filter-history training study

| Source | Tracking gain vs LQR | Heading change | Rate RMS change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.00% | +0.00% | 96/96 |
| negative | +1.029% | -3.30% | +3.24% | 96/96 |
| positive | +1.029% | -3.30% | +3.24% | 96/96 |
| student | +2.032% | -0.28% | +3.10% | 96/96 |
| v3ppo | +2.584% | -0.48% | +4.29% | 96/96 |
| nohistory | +2.956% | -0.52% | +4.73% | 96/96 |
| history | +2.979% | -0.50% | +5.13% | 96/96 |

Selected arm: None.

New interface causal_filter_history_v5 explicitly assigns14 to past filtered residual/0.08;15/16/17/19 remainzero. All original models are logit-preserving bridges with input14ignored. Same fixed supervisor, objective and extra training budget in both ablation arms. Existing v3 training/pretraining are extra; no per-seed checkpoint/arm selection. Finite development success is not unseen or physical validation.
