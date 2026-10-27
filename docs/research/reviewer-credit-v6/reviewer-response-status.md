# Status against the twelve original reviewer concerns

This is an internal evidence checklist, not a response sent to the journal.
The rejected paper is not made acceptable merely by adding a supervisor label.

| Concern | Current disposition |
|---|---|
|1. Limited novelty / neuro-symbolic label| Open. A freshness/cost predicate and predictor do not by themselves establish novelty or formal symbolic reasoning. No stronger claim is made. |
|2. Exogenous latency reward| Current training uses actual tracking, heading, actuator-rate, command-effort and failure rewards; no reward pretends that a steering action controls externally injected computation stalls. |
|3. Delay mechanism unclear| Offline delivery queues enforce at least one polling tick; real workers actually wait after inference. Request identity, observation/start/inference/send/receive/commit timestamps are logged. Configured total logical service and real post-inference wait are not treated as identical distributions. |
|4. LQR delay-margin contradiction| PPO-worker unavailability with fresh local-state LQR is distinguished from delayed LQR feedback. No claim that LQR feedback itself tolerates one second is retained. Local OS stalls remain a timing gap. |
|5. Unfair 49-fold speed comparison| The old claim is not retained. Actual inference, service wait, packet age, release lateness, processing and total response are separate. A simulation period is not PPO inference time. |
|6. Implausible ablation frequencies| Current comparisons share plant, observation, actuator limits, supervisor and delay rules, with raw traces and original-target timing. Removing a reward term is not credited with changing inference from100Hz to4930Hz. |
|7. Nominal degradation / PPO value| Balanced development gains over LQR exist, but complete student-relative selection still fails. The submitted-action ablation improves its matched all-actions control, not enough to establish the required additional PPO value. All outcomes are preserved. |
|8. Overstated generalization| Fresh noise on known mirrored paths is development evidence. Reserved unseen-path confirmation remains unopened on failed selection/timing. No broad generalization claim is made. |
|9. Incomplete stability proof| Bounded corrections, software survival and stale rejection are not a global convergence proof. The separate bounded-error scalar safety-filter contract has declared assumptions and cannot certify the noisy nonlinear vehicle. |
|10. Missing method details| Frozen protocols, reward equations, categorical five-action outputs, seeds, budgets, model/source hashes, observation semantics, optimizer settings and full raw comparisons are preserved. Three groups remain limited statistical evidence. |
|11. Unfair energy/blind-distance comparisons| No GPU/CPU energy or total sensing-to-actuation blind-distance superiority is claimed without matched physical measurements. |
|12. Numerical/reference inconsistencies| Independent replay recomputes metrics and action decisions. All32 original reference entries were structurally reviewed; five supplied primary-source entries are verified. Remaining publisher/primary metadata and citation-to-claim checks are open. |

The resulting evidence report remains a draft. Full selection, target timing,
matched robust vehicle reproduction, reserved/native confirmation and physical
validation cannot be marked complete from these software checks.
