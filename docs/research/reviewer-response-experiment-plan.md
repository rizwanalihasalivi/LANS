# Reviewer-driven residual LANS experiment plan

Scope: original LQR baseline + PPO residual + predictive rule-based supervisor.
Full-command PPO/LQR switching is outside this campaign. No original manuscript
speedup, energy, safety, or delay-tolerance number is inherited as verified.

## Required evidence for the twelve reviewer comments

| Comment | Required action / completion evidence |
|---|---|
| 1 Novelty and neuro-symbolic terminology | Compare with residual control, predictive filtering and runtime assurance; specify predicates, states and transitions. Terminology alone earns no novelty. |
| 2 Latency reward | Do not claim independent random delay is controlled by steering. Identify action-dependent reward effects and compare with the latency penalty removed under matched training. |
| 3 Actual delayed execution | Retain request/observation timestamps, queue rules, delivery and applied commands; plant advances while proposals are unavailable. Distinguish simulated service delay from OS timing. |
| 4 LQR delay contradiction | Separate delayed PPO service from sensor/local-loop delay. Test timely local execution separately; no claim of one-second delayed LQR feedback tolerance. |
| 5 Fair timing | Warm comparable policies, same CPU/threads/input shape, separate computation from control period, queueing and IPC. Preserve raw samples. |
| 6 Credible ablations | Measure every ablated implementation; do not substitute 100 Hz simulation rate for inference duration. |
| 7 Benefit over LQR | Report paired strong LQR and same-gate fixed positive/negative proposals, regional degradation, heading and steering tradeoffs. |
| 8 Generalization | Distinguish known-path fresh noise from unseen paths; reserve separate paths before design selection. |
| 9 Stability | Restrict nominal LQR analysis to its assumptions; bounded residual does not imply zero convergence. No switched nonlinear safety guarantee without proof. |
| 10 Reproducibility | Freeze reward terms/weights, policy distribution, features, queue/holding rules, baselines, seeds and statistics; archive source/model hashes. |
| 11 Energy / blind distance | Remove unsupported GPU comparisons. Computation travel distance is not total sensor-to-actuator delay. |
| 12 Numerical / references | Recompute tables from raw data, verify citations and align units, thresholds, equations and claims. |

## Stage A: archived checkpoint diagnostic (not corrected-interface validation)

Runner: `tools/controller_review/reviewer_pilot.py`.

Predeclared 90 fresh DEVELOPMENT episodes: three archived PPO training seeds,
20 m/s, two known paths, nominal / 20 ms / 100 ms simulated service, and five
methods: LQR, fixed +/-0.04 rad, scratch PPO 100k, fine-tuned PPO 100k.
All candidates use the unchanged legacy predictive gate. All endpoints are
reported; no checkpoint selection, retraining, threshold tuning or reserved
evaluation. New noise base 1046000000. The executable writes its protocol and
source hashes before rollouts, plus model hashes, all traces and raw metrics.

Historical checkpoints use the old 20-feature interface, including simulated
pending/forecast channels subsequently removed from the causal profile.
Consequently this stage is only a checkpoint/infrastructure diagnostic. It
cannot establish deployable causal PPO benefit; setting those channels to zero
also cannot establish that without addressing distribution shift.

## Subsequent stages (not completed by Stage A)

1. Freeze a causal PPO training/runtime contract and balanced full-episode metrics.
2. Predeclare matched original-gain / predictive-supervisor / fixed-residual
   ablations, training budgets and development acceptance criteria.
3. Run bounded causal PPO pilots; preserve negative results and stop rules.
4. Only after development selection, freeze independent confirmation and unseen
   paths. Native Webots and actual process deadline tests are separate evidence.
5. Vehicle readiness and formal safety remain outside demonstrated claims.

## Stage A outcome

The [90-episode diagnostic](reviewer-pilot-2026-10-26/README.md) completed.
All episodes survived and all 24 non-LQR severe-delay pairs reproduced LQR
commands/trajectories exactly. Archived fine-tuned PPO reduced aggregate error
by 3.755% versus LQR in this narrow grid, but the historical input interface and
missing initialization arm prevent any deployable causal-policy or incremental
fine-tuning claim. This is not a resolution of all twelve reviewer objections.
