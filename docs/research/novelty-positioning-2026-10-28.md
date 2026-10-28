# LANS: a bounded novelty claim against the supplied primary papers

**Current conclusion:** a first-of-its-kind control algorithm has not been established. The strongest candidate methodological contribution is the joint handling of residual-packet expiry, incremental predicted benefit over fresh-state LQR, and recovery-limited residual authority in asynchronous vehicle control. Its implementation and experimental analysis are contributions; global originality and balanced performance superiority remain open.

This assessment rereads the supplied primary versions, not a comprehensive search of all2026 literature. Absence from the selected papers' described formulations is not proof that no other paper uses a similar method. No published-controller benchmark is implied.

## Established prior work and the specific proposed distinction

| Primary work | What it already establishes | LANS distinction to investigate; not an inferred inability of the prior method |
|---|---|---|
| Wabersich & Zeilinger, arXiv1812.05506v4,2021 | Predictive filtering of a proposed input, state/input constraint satisfaction, uncertainty treatment and backup/terminal constructions. Related work explicitly discusses Simplex advanced/backup switching. | LANS's performance gate compares a bounded residual's incremental predicted tracking cost against LQR, with packet freshness and lifecycle checks. This is a different objective/execution contract, not a stronger safety guarantee. |
| Tearle et al., arXiv2102.11907v1,2021 | Predictive safety filtering for vehicle racing, safe backup sequences, invariant terminal-set construction, input-rate regularization and miniature-vehicle experiments. SectionIII Eq.(5) already penalizes input changes. | Steering smoothing, prediction, neural filtering and fallback cannot themselves be claimed as new. The candidate distinction is evaluating expiring asynchronous residual assistance relative to a continuously available tracker. |
| Kalaria, Lin & Dolan, arXiv2208.13856v1,2022 | Computation/processing/actuator-delay handling, adaptive computation-time estimation, buffered two-level control, robust tube MPC and a guard for learning-enabled commands. See SectionsIII-G/H/I. | This is the closest computation-delay vehicle comparison. LANS investigates optional residual authority, expiry/rejection and recovery while fresh-state LQR remains available. Neither delay compensation nor separate high/low-level execution is a new principle. No lower computational cost or better robustness is established without matched tests. |
| Cano Córdoba et al., ICAPS2023, Safety Shielding under Delayed Observation | Formal safety-game synthesis for delayed observations, worst-case assumptions, corrective-action selection and CARLA examples. | LANS isolates delayed neural-worker availability with fresh local baseline sensing. This differs from the paper's delayed-observation problem formulation; it does not imply their general approach could never cover related execution delays. LANS does not inherit the formal shield guarantee. |
| Tabrizian et al., arXiv2403.11852v5,2026 (DAROM) | RDMDP observation-delay modeling, masked action history, a delay-aware SAC encoder and a physics-based action supervisor for V2I-assisted merging. SectionIII-B explicitly assumes random observation delay but no action delay; the agent's action is applied immediately. | LANS studies computation-delayed residual availability in lateral path tracking, with a separate fresh-state LQR. Delay-aware learning, causal history and physical fallback are already established; changing SAC to PPO is not sufficient novelty. |

Residual reinforcement learning itself is established prior art. Its original primary papers and broader age-aware control/runtime-assurance literature need inclusion in a systematic novelty search; the five supplied papers do not exhaust those families.

## The most specific candidate mechanism

At a local control decision, retain the proposal's original observation timestamp and determine whether it is still eligible. Evaluate the baseline and the proposed fused command from the same current estimated state, including the actuator, reference preview and physical constraints. In the candidate rollout, allow assistance only over the currently available packet's remaining eligible control steps; then continue with LQR, without assuming that another neural response will arrive. Assess a correction at the authority that is permitted when it is admitted. Qualification and gradual recovery use distinct valid packets, while stale assistance immediately loses authority at control decisions.

**Example:** with a50ms freshness cutoff, a proposal that is already40ms old can assist for one remaining10ms control step in the rollout, followed by LQR. Predicting that this same residual remains active for an entire1s horizon would credit assistance that the execution rules will not permit. Conversely, being fresh alone is insufficient: the candidate must also improve the declared predicted objective over LQR.

This is narrower than "we combine PPO and LQR" or "we add a symbolic supervisor." It combines three concrete elements:

1. **Remaining validity affects prediction**, not just a scalar latency weight.
2. **Incremental value is baseline-relative**, using the physically constrained command and admissible authority.
3. **Execution and recovery are part of the decision contract**, with original timestamps, distinct requests, immediate revocation and auditable reasons.

None of these elements is asserted to be universally unprecedented in isolation. The exact joint rule is a candidate incremental-method contribution whose closest prior-art overlap must still be resolved. Timestamp hygiene and stale-packet rejection are important correctness properties, not automatic algorithmic novelty. Matched student/fixed-residual ablations provide attribution, not proof of originality.

## Implementation and evidence boundaries

- `tools/reviewer_v8/recovery8.py`: distinct qualifying packet recovery and remaining-life calculation.
- `tools/reviewer_v10/rollout10.py`: common nominal constrained rollout, assistance only during eligible steps and LQR continuation;100×10ms vehicle-cost horizon.
- `tools/reviewer_v12/forecast12.py`: separate causal neural-response compensation, capped40ms. This forecast is not itself a new delay-compensation principle.
- These are components of the versioned predictive residual line. The recovered-PPO v13 study is a separate historical latency-gain/smoothing/rate-projection diagnostic; its results must not be used as validation of this complete predictive mechanism.
- Existing tests demonstrate code execution and particular fallback behavior. They do not establish robust vehicle safety, hard real-time scheduling or a globally new algorithm.
- Current learned variants have not passed all frozen tracking, smoothness and strong-baseline criteria. The latest v13 outcome remains negative for full promotion; see its preserved [report](recovered-ppo-v13/README.md).

## Evidence needed for a stronger novelty statement

1. Compare the exact rule with the nearest residual/performance filters, networked age-aware controllers and runtime-assurance methods, including later papers; document actual overlaps rather than blank feature checkboxes.
2. Isolate remaining-lifetime prediction from other changes: same learner, data, reward, predictor, recovery and timing, with only expiry handling changed. Earlier bundled fixes do not isolate this causal effect.
3. Compare the same gate with PPO, its supervised student, fixed corrections and a strong feasible model-based alternative; retain rejected/failed outcomes.
4. Analyze a precise property under explicit assumptions, or limit the contribution to an empirical method/system study. Predicted benefit is not guaranteed realized benefit or an invariant-set proof.
5. Demonstrate useful tracking/smoothness and execution trade-offs in independent confirmation. A successful different scope or task is not proof that a limitation in the published methods has been fixed.

## Reviewer-facing wording

> We investigate a supervisory rule for asynchronous residual vehicle control that evaluates the incremental predicted benefit of a currently available neural proposal over fresh-state LQR, accounting for the proposal's remaining validity and the residual authority permitted during recovery. The proposed contribution is the joint treatment of packet expiry, applied-command prediction and recoverable learned authority under worker delays, evaluated against matched nonlearned alternatives. We do not claim a new PPO or LQR algorithm, a formal safety guarantee, or established superiority to the cited controllers. The originality of this particular combination and its practical benefit require the stated comparative evaluation.

## Primary versions checked

- [Wabersich & Zeilinger,1812.05506v4](https://arxiv.org/abs/1812.05506v4): abstract, introduction, related work and predictive-filter formulation.
- [Tearle et al.,2102.11907v1](https://arxiv.org/abs/2102.11907v1): abstract, SectionsI/III/VI; notably the smoothing objective in Eq.(5).
- [Kalaria et al.,2208.13856v1](https://arxiv.org/abs/2208.13856v1): contributions, SectionIII-G buffered computation-delay handling, estimation and learning-enabled guard.
- Cano Córdoba et al., supplied ICAPS2023 proceedings pp.80–85: abstract, delayed safety-game synthesis and interference-minimizing corrections; exact metadata in [verified references](reviewer-interface-v4/verified-references.md).
- [Tabrizian et al.,2403.11852v5](https://arxiv.org/abs/2403.11852v5): abstract, architecture and SectionIII-B observation-delay/no-action-delay assumption.
