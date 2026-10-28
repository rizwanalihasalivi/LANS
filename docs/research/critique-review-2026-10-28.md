# Review of the supplied AI critique against available LANS evidence

Reviewed: the author's uploaded `Pasted text(20261028-060517).txt`, current versioned controller sources, the completed recovered-PPO v13 experiment, and the supplied Wabersich–Zeilinger primary PDF (arXiv:1812.05506v4). The critique is an opinion document, not a reviewer decision, verified literature survey, or instruction to change the architecture. Its claim to have read a particular entire bilingual proposal is not independently established here.

**Assessment:** its central concerns about incremental novelty, unsupported neuro-symbolic terminology, arbitrary-looking thresholds, supervisor overhead and unproven PPO advantage are useful. Some factual statements are wrong or mix different implementation versions. Its positive claims about originality, comprehensive references and degree/publication suitability also require qualification.

## Claim-by-claim assessment

| Critique statement | Assessment | Evidence / appropriate response |
|---|---|---|
| The main problem is asynchronous aged residuals with fresh independent LQR control | Accurate for the residual architecture | It is not the earlier proposed full-command PPO-to-LQR switching architecture. Keep those designs separate. Observation age includes more than inference time. |
| Explicit proposal age is genuinely new or rare | Novelty not established | Time-stamped control, age of information, delay-aware control and runtime assurance are existing areas. A specific vehicle residual-control combination may be a contribution, but this requires a bounded primary-source comparison, not an AI assertion of absence. |
| Neuro-symbolic is loosely justified | Valid concern, not a categorical prohibition | Explicit predicates, state transitions and auditable rule decisions support an operational neural-plus-rule architecture. They do not by themselves establish learned symbolic knowledge, theorem proving or formal safety. Define the limited meaning, give the actual rule/state specification and ablation, or use a narrower descriptive label. Adding a supervisor box alone is insufficient. |
| The method integrates known components | Substantially accurate | PPO, LQR, filtering, timestamps and fallback are not individually new. The contribution must be the specified asynchronous contract, decision method and evidence of useful trade-offs. Reproducibility is valuable evidence quality, not itself proof of a new control algorithm. |
| 50ms and40ms need justification | Valid | Keep them configurable and explicitly empirical until supported by predeclared sensitivity tests. Freeze chosen values before independent confirmation. An age sweep must distinguish eligibility, actual authority, tracking, failures and processing cost. No theoretical delay margin follows from either constant. |
| The supervisor's predictive comparison horizon is40ms | Incorrect for the current versioned predictive implementation | In v7–v12,40ms caps the causal neural-response compensation forecast. `rollout10.rk_cost` evaluates100×10ms=1s of nominal vehicle cost; current-packet assistance lasts only until expiry, followed by LQR continuation. The v13 historical-profile repair instead uses a separate10ms actuator prediction. These are three different horizons. A proposal may choose a different horizon, but it must not describe these as identical implemented settings. |
| Recovery means three consecutive control ticks | Outdated for v8+ | Recovery requires three distinct qualifying packet sequence numbers. Reusing one packet does not count three times. Authority is zero on every stale tick; qualifying recovery memory is retained only within a bounded liveness interval. This repaired a real40ms/recovery interaction. |
| No runtime budget has been specified | Partly outdated, underlying concern valid | The versioned guard checks scheduled tick+9ms to reserve approximately1ms of a10ms loop and suppresses new forecast/gate work at that boundary. This is a heuristic reserve, not worst-case execution time or preemption of an already-running rollout. Later fallback cannot undo a missed physical deadline. Separate-process PPO also does not guarantee independent CPU scheduling. |
|100ms worker inference implies90% LQR and10% PPO | Incorrect under the stated50ms freshness rule | If every response is at least100ms old at arrival, every response is stale. After any previous eligible packet expires, learned authority is zero:100% LQR while this condition persists. A100Hz loop and10Hz worker completion rate do not imply10% learned authority. |
|95% rejected proposals imply PPO is useless | Not a valid inference by itself | A few well-timed interventions could matter. Measure eligible requests, accepted distinct packets, assisted control ticks, integrated authority, tracking/smoothness and matched ablations separately. In current experiments, full useful balanced PPO superiority remains unproven for substantive outcome reasons. |
| Wabersich–Zeilinger PSF was designed for collision avoidance | Too narrow / misleading | The supplied paper's abstract and introduction concern state/input constraint satisfaction for nonlinear systems under uncertainty. Examples include a pendulum and quadrotor; vehicle collision avoidance is not its sole purpose. LANS's nominal cost improvement gate does not inherit its safety theorem or terminal/backup feasibility assumptions. |
| Cost weights should not be adjusted after seeing test results | Valid | Existing versioned protocols freeze budgets, weights and selection rules before each fresh development comparison, while preserving failed outcomes. Repeated development remains development; final independent confirmation is still needed. Research hypotheses may change between disclosed experiments, but old outcomes must not be relabeled. |
| Drop Webots to save effort | A scheduling suggestion, not a scientific necessity | Retain a focused independent-dynamics confirmation for the eventual frozen controller. A self-written predictor and plant can share assumptions or bugs. Avoid a large native grid before a controller qualifies, but eliminating cross-simulator confirmation weakens the empirical claim. Webots itself is not physical vehicle validation. |
| No Lyapunov proof makes the thesis inadequate, or integration guarantees master's suitability | Neither conclusion follows automatically | Requirements belong to the institution and committee. An empirical systems study can be defensible with appropriately limited claims. Global stability, zero-error convergence, formal safety or guaranteed timing require corresponding analyses and assumptions; finite survival does not establish them. |
| All21 references are relevant and verified; publication tier can be predicted | Unsupported as a blanket conclusion | Five supplied primary PDFs have version-specific verification. A prior32-entry manuscript audit was structural, with unresolved metadata and claim mappings. That does not certify every reference in a different21-reference proposal. Venue/degree outcomes cannot be inferred from this AI assessment. |

## What the completed recovered-PPO experiment adds

The historical7.685% result has been reproduced across all three paired actors:144 original episodes and187,200 transitions. PPO steering-rate RMS was83.30% above LQR; the student had better tracking but also failed smoothness. This is evidence of a real trade-off, not a corrupted headline number.

Audit findings include training inside predictive admission but evaluating the recovered actor under age-only gain, a command-increment reward versus an executed-actuator-rate metric, and discontinuous high-authority residual corrections. These establish mechanisms and mismatches, not a single proven explanation for every inferior PPO decision.

The isolated repair experiment added smoothing, tested a local actuator-rate projection, and performed six matched100k-step training continuations (600k new steps). All2160 fresh episodes and2,913,042 recorded transitions were replayed;1,572,762 neural queries and396 exact100ms fallback comparisons were checked.18 contract tests passed. Three experimental episodes violated the survival criterion; they are retained, not removed.

| Fresh-grid method | Tracking gain vs LQR | Actuator-rate RMS change vs LQR |
|---|---:|---:|
| Recovered original PPO | +2.8508% | +62.151% |
| Smoothing-only PPO | +5.6541% | +25.041% |
| Same-smoothing student | +5.8364% | +25.485% |
| Local-rate projection, original PPO | −3.4488% | +26.325% |
| Local-rate projection, legacy-reward retraining | −5.8541% | +21.375% |
| Local-rate projection, actual-rate-reward retraining | +2.2528% | +12.800% |

The final physical-reward arm survives180/180 episodes and beats its same-wrapper student by5.9178% in the aggregate, but loses to that student in two of three paired groups (−3.2032% and−3.6471%). The first group's large aggregate gain is also affected by the same-wrapper student's failed tyre-stress episode. This is not repeatable PPO superiority. Its steering-rate increase still exceeds the frozen5% allowance. No v13 candidate passes the full selection screen or the20% target; no controller is promoted.

The projection illustrates an additional caution: limiting predicted motion relative to LQR at the **current candidate trajectory state** does not bound episode RMS relative to a **separate LQR trajectory**, or guarantee tracking survival. The original-PPO/student/legacy-retrained projection variants each failed one25m/s tyre-stress episode. They remain experimental failures. No new wall-clock, native Webots, laptop or physical validation was performed here.

Fresh-grid gains must not be directly substituted for the historical7.685% figure: the new grid includes three speeds and a one-tick10ms service diagnostic. See the complete [v13 report](recovered-ppo-v13/README.md), [interpretation](recovered-ppo-v13/INTERPRETATION.md) and [selection record](recovered-ppo-v13/decision.json).

## Recommended response to the critique

1. Accept the questions on thresholds, runtime budget, cost-weight selection and additional learned value. Answer with versioned methods and evidence, not stronger adjectives.
2. Correct the100ms authority calculation, recovery semantics, compensation-versus-comparison horizon, and characterization of predictive safety filtering.
3. State candidate contributions as hypotheses to evaluate: a causal asynchronous residual contract; explicit freshness/validity/recovery decisions; latency and execution fault handling; and matched evidence isolating learned benefit from the supervisor. Do not present these as proven firsts or proven performance gains.
4. Keep strong LQR, supervised-student and deterministic-residual controls. Do not weaken them, relax the frozen smoothness threshold or select favorable seeds to obtain10–20% gains.
5. Retain focused native confirmation after a development candidate qualifies. Report unsuccessful development and timing tests, and separate computational-worker stalls from delayed LQR feedback.

## Checked sources

- `tools/reviewer_v8/recovery8.py` and `protocol.json`: distinct-proposal recovery, expiry and1ms runtime reserve specification.
- `tools/reviewer_v10/rollout10.py`:100-step nominal cost rollout, actual average actuator-rate cost.
- `tools/reviewer_v10/runtime10.py` and `tools/reviewer_v9/runtime9.py`:9ms budget guard,10ms original deadline and post-computation rejection.
- `tools/reviewer_v12/forecast12.py`:40ms causal response-forecast cap; not the vehicle comparison horizon.
- `tools/reviewer_v13/protocol.json` and `docs/research/recovered-ppo-v13/`: frozen recovery experiment and raw verified outcomes. Core experiment commit:`3fab1949b826132b15b841f1b495df88f7abbcc3`.
- [Verified supplied primary references](reviewer-interface-v4/verified-references.md) and [prior manuscript structural bibliography audit](reviewer-credit-v6/bibliography-audit.md).
- K.P. Wabersich and M.N. Zeilinger, [arXiv:1812.05506v4](https://arxiv.org/abs/1812.05506v4),17May2021, abstract and introduction, supplied PDF pages1–2. This primary source was reread for this review; it does not constitute a comprehensive literature search.
