# LANS causal-history correction and matched training results

27 October 2026 (Asia/Shanghai). Evidence update; no claim that all requirements passed.

## Implemented input correction

The earlier 20-channel input did not explicitly contain the residual-filter memory. The new, separately versioned interface is causal_filter_history_v5. Channel 14 now carries the known stored filter value divided by 0.08 at query time. It is not an unknown pending proposal. Future-output/completion/service channels 15/16/17/19 remain zero. This makes filter history available but is not a proof of full Markov observability, optimality or physical safety.
$$h_t=f_{t^-}/0.08,\qquad h_t\in[-1,1].$$
All original TRAIN normalization is retained except the explicitly new history coordinate: mean 0/std 1 after physical scaling, chosen from filter bounds rather than fitted on DEV. The old unused input column is zeroed at initialization, preserving legacy actor logits for arbitrary history. A matched no-history arm keeps that column exactly zero. Runtime guards reject mixing legacy and history model/controller ABIs.
The two arms share architecture, controller, reward, seeds,100,000 additional transitions per model, optimizer and 0.005 entropy coefficient. Both start from the same frozen v3 actor, which already includes 100,000 PPO transitions plus original supervised pretraining. The new critic is initialized identically per pair. The history arm observes filter history; the ablation sees channel 14 zero during training. At evaluation all methods receive the same history interface, with original/no-history actors ignoring 14 exactly.
There are no controller, reward-weight or threshold changes from the corrected v4 freshness variant. Nominal service remains at least one 10 ms polling tick. The fixed 10 ms PPO rollout can sample ignored actions while busy, a remaining credit-assignment limitation. No-history/history model budgets are matched; a comparison against the older frozen model includes extra training and is not attributed solely to the new input.

## Fresh matched development results

All six pilots completed their fixed endpoints: **600,000 additional transitions**. All 672 development episodes survived. Three paired model/noise groups,15/25 m/s, two known paths, mirrored directions and nominal/tire/20 ms/100 ms cases were used. These are development results, not unseen-path confirmation.

| Source | Lateral RMSE m | Gain vs LQR | Heading change | Rate RMS change | Survival |
|---|---:|---:|---:|---:|---:|
| LQR | 0.090449 | +0.000% | +0.00% | +0.00% | 96/96 |
| Fixed −0.04 | 0.089518 | +1.029% | -3.30% | +3.24% | 96/96 |
| Fixed +0.04 | 0.089518 | +1.029% | -3.30% | +3.24% | 96/96 |
| Student | 0.088612 | +2.032% | -0.28% | +3.10% | 96/96 |
| Frozen v3 PPO | 0.088112 | +2.584% | -0.48% | +4.29% | 96/96 |
| PPO, no history | 0.087776 | +2.956% | -0.52% | +4.73% | 96/96 |
| PPO, history | 0.087755 | +2.979% | -0.50% | +5.13% | 96/96 |

The no-history arm gains **0.943%** over the student; the history arm gains **0.967%**. Neither reaches the frozen 1% student margin. The history arm also exceeds the 5% actuator-rate limit. These near misses are failures, not rounded passes.
The history feature therefore does not show a clear balanced performance advantage in this study. Additional training helped on this development grid, but the feature itself is not credited with that entire improvement. The no-history weights for the new coordinate stayed exactly zero; history-arm weights changed. Three groups are too few to establish a robust population effect from small mean differences.

**Selected arm: None. Reserved tests remain unopened.** Exact failed criteria follow:

- nohistory: lacks 1% gain vs student
- history: lacks 1% gain vs student; rate_rms_rad_s >1.05 LQR

The independent verifier replayed **922,992 transitions**, **342,864 submitted model decisions**, full observations including causal history, rewards, observer/plant states, filtering and commands. All 144 severe-delay/LQR trajectory pairs matched exactly. No per-seed checkpoint or arm mixing was used.

## Runtime and package verification

The package contains the **nohistory** arm as a research diagnostic. It is not a promoted winner. The no-history arm is the balanced diagnostic fallback when no arm qualifies; its new-interface history coordinate is available but ignored by its zero weights.
Torch/NumPy class parity was checked for 24,300 archived observations per actor, with nonzero declared causal-history test values. This is export parity, not new performance data or parameter fitting. The clean Python 3.10 kit uses only NumPy/SciPy/Numba/Gymnasium and standard library at runtime; no Torch/GPU is required.
The package smoke ran 1500 software-plant ticks and recorded 274 original 10 ms deadline misses. Functional checks: **True**. Observed timing: **False**. Actual returned packets were independently replayed against the source Torch actor and the physical observation/filter-history fields.
The earlier v4 experiment validated real worker stall/recovery for three actor seeds and separately recorded full-controller timing failures. The independent native C heartbeat missed 80/3,000 deadlines even without a neural/controller workload. Those earlier numbers are not relabeled as timing validation of the new models. A new-model smoke is also not a complete selected-winner real-time validation.
LQR and the supervisor share the local process. Independence from the PPO worker does not isolate local control from sensing, supervisor, IPC or OS scheduling delay. Late/stale-action rejection does not guarantee that a replacement LQR command reached a physical actuator before its deadline. A defined target execution/OS isolation design and physical measurements are still required.
Offline 20 ms cases represent total configured logical service. A real 20 ms post-inference wait also includes inference, IPC and polling latency. The distributions are not assumed identical. Software timestamp fields are clock reads around software events, not hardware wire or sensor timestamps. Fixed-step plant survival cannot establish continuous physical safety while the host is stalled.

## Remaining requirements

- Demonstrate the unchanged full scientific selection criteria on a justified new development design; the 1% margin is not a code bug that can be repaired by lowering it. No additional training extension or hyperparameter search was run after these outcomes.
- Establish original 10 ms execution on the actual target. The user laptop has not been remotely executed. Run the extracted kit using the top-level RUN_WINDOWS.cmd, or `bash RUN_MAC.command`, and retain laptop-results/Results.zip. Current cloud timing failures are not a Windows/macOS result or a hard-real-time guarantee.
- Only after full selection and corresponding-controller timing pass, freeze/run reserved unseen-path and native Webots confirmation. Previous native interface checks are not new-model confirmation.
- Complete the full robust published-controller reproduction and broader bibliography verification. The existing nominal safety-filter specialization and five primary-source entries are scoped evidence, not the complete robust algorithm or a systematic prior-art review.
- Physical sensors, communications and actuator validation require connected hardware. No real-vehicle readiness, global stability, energy/blind-distance advantage or 49-fold inference-speed claim is made.
- The revised evidence draft is reviewable but is not declared submission-ready. Novelty and the label neuro-symbolic are not established merely by adding predicates or a predictor block.

The prior causal/interface/compute correction studies remain preserved, including all failed outcomes. Reproduce/resume with `python tools/controller_review/run_history_work.py --publish`. This command does not manufacture missing laptop/vehicle measurements or open reserved tests on failure.
