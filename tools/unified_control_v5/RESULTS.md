# Integrated corridor repair: executed evidence

The four reported engineering limits are repaired on the recorded Python
grids. Corridor failures are eliminated on the original development and
communication-stress cases, observed collisions remain zero, and hybrid mean
RMSE now improves on the shared optimized reference. The separate statistical
promotion criteria remain unmet. This is a development result, not final
held-out, native Webots, physical-safety or PPO-superiority evidence.

## Reported failures: same-case regression

| Hybrid outcome | Historical v3 | Repaired v5 |
|---|---:|---:|
| Original development corridor/episode failures | 19/96 | **0/96** |
| Original communication-stress failures | 14/72 | **0/72** |
| Observed collisions in those runs | 0 | **0** |
| Fresh development failures | — | **0/96** |
| Fresh communication-stress failures | — | **0/72** |

Each denominator includes all three frozen actors, seeds 42/43/44; actors and
mirrored cases are correlated and are not 96 independent trials. No failing
case, checkpoint or actor was dropped. The corridor remains 1.75 m. An episode
with a corridor violation still fails even without a collision. Steering,
braking, delay, freshness, failure penalty and all numeric promotion thresholds
are unchanged. Episode lengths are six seconds, not long-duration guarantees.

## Fresh v5 development: all methods retained

| Method | Mean failure-penalized RMSE (m) |
|---|---:|
| Shared calibrated LQR | 0.079350122 |
| Fixed residual | 0.079350122 |
| Deterministic correction | 0.079136767 |
| PPO proposal branch | 0.079160067 |
| Optimized nominal reference | **0.076527800** |
| Adaptive planner without PPO | **0.076263729** |
| Integrated hybrid, all three actors | **0.076249187** |

Lower is better. References each use 32 matched cells; PPO and hybrid include
three actors per cell. The nominal optimized reference receives the same
calibrated baseline, candidate grid and nonlinear planner. The adaptive-only
ablation shows that most of the advantage over that reference comes from
model adaptation/planning. These results do not establish a significant extra
PPO benefit or equal online compute between methods.

| Unchanged promotion requirement | Measured v5 result | Status |
|---|---|---|
| At least 5% mean gain versus LQR | 3.907915%; 95% CI [2.426474, 5.221135]% | **FAIL** |
| At least 1% mean gain versus optimized | 0.364069%; 95% CI [-0.163133, 1.182885]% | **FAIL** |
| Positive lower CI versus optimized | -0.163133% | **FAIL** |
| Every actor improves versus LQR | 3.913998%, 3.878716%, 3.931030% | PASS |
| No hybrid corridor/collision/early-termination failure | All four stages: zero | PASS |
| Heading/rate mean increase at most 10% | No violation | PASS |
| Per-cell progress at least 99% of matched LQR | No violation | PASS |

Intervals use the original fixed 5,000-draw bootstrap over eight
scenario/speed clusters. A better observed mean does not prove statistical
superiority when its gain interval includes zero. Final reserved cases, formal
multi-actor wall-worker confirmation and native Webots are **NOT_RUN** because
prerequisites fail. No Python metric is presented as a Webots result.

## What changed

The shared LQR was oscillating under steering-rate limits. A declared
training-only search selected R=16 from 1/4/16/64, and a separate training-only
lookahead calibration selected 1.0 s from 0.25/0.5/1.0 s. Every comparator
receives these same settings. Predictive admission now checks the corridor,
multiple model hypotheses, and heading/rate budgets as well as traffic clearance.

A causal observer fits stiffness from validated successive ego packets and
actual applied commands; fixture truth never enters control. Consistent
feedback/prediction and constrained predictive plans improve tracking during
mismatch. V5 corrects the linear planner's constant-speed approximation with
nonlinear plan projection/refinement using bounded supervisor braking.

During ego blackout, stale packets remain stale and cannot enter PPO. A bounded
2.5 s dead-reckoning stopping backup reconstructs steering from the original
packet plus complete applied-control history while applying maximum legal
braking. Missing history or expiry falls back explicitly. These are engineering
assumptions about the simulated dynamics, not a certified uncertainty bound.

All three original 32,768-step policy endpoints are reused, with **zero new
training steps**. V4 and v5 each have a pre-run source/model/protocol freeze and
their own fresh development initialization namespace. V5 follows inspected v4
development results and is not a blind replication. Their fresh means are not
a paired causal comparison; the original failure regression uses the same cases.

## Execution and integrity

Each formal version contains 752 episodes and 90,240 replay-audited ticks:
160 original-development regression episodes, 120 original-stress regression
episodes, 352 fresh development episodes and 120 fresh stress episodes. The
training-only calibration adds 256 episodes, and lookahead calibration adds
384 episodes; these are not confirmation evidence. Intermediate probes and
both failed promotion decisions are preserved.

The final focused Python suite passes **71 tests**. It checks original
contracts, physical limits, causal identification, stale-data backup,
Python/compiled physics equivalence and constrained nonlinear planning.

Actual spawned-worker diagnostics use the same repaired controller and fixed
seed 42, not a selected best actor:

| Functional check | Completed ticks | Corridor/collision counts | >50 ms input-to-issue / cycle misses | Max input-to-issue |
|---|---:|---|---|---:|
| Nominal following | 120/120 | 0 / 0 | 0 / 0 | 30.536 ms |
| Curved ego blackout | 120/120 | 0 / 0 | 0 / 0 | 42.264 ms |
| Merge worker crash | 120/120 | 0 / 0 | 0 / 0 | 18.685 ms |

Timing includes input processing, feature reconstruction, identification and
planning through command issue; matrix/JIT startup is separately recorded.
These three six-second checks are explicitly functional diagnostics, not
general runtime guarantees. The first nominal attempt completed its raw trace
but summary serialization failed on a NumPy integer. That trace, exception and
source bytes are preserved; the rerun follows the serialization-only repair.

## Review and reproduce

The [implementation/run instructions](README.md) name the supported v5 entry
points. [Evidence manifests and archives](evidence/) preserve calibration,
all v4/v5 raw trajectories, snapshots, gates, logs and diagnostic attempts.
Every archive has an outer SHA256 and an internal per-member SHA256 manifest.
The policies and earlier failed studies remain in
[`python-results-v2-v3.zip`](../unified_improvement/evidence/python-results-v2-v3.zip).
Extract archives into the repository root to restore their original paths.

```bash
python -m tools.unified_control_v5.verify_evidence
# In the pinned Python 3.10 environment, after restoring evidence:
python -m tools.unified_control_v5.verify_evidence --campaigns
python -m pytest tests integrations/unified_lans/tests \
  tools/unified_campaign/test_campaign.py tools/unified_improvement/test_verify.py \
  tools/unified_control_v4/test_control.py tools/unified_control_v5/test_control.py -q
```

The remaining work is to demonstrate a repeatable gain meeting the original
statistical targets in a new declared development experiment, then pass the
untouched reserved and formal runtime gates before transferring this exact
controller to final Webots tests. No target was relaxed to mark this work passed.
