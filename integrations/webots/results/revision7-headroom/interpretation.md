# Step1 outcome: useful bounded headroom, not an absolute ceiling

The environment was ready and the frozen diagnostic has completed. It evaluated **864 paired episodes**, without neural training or changing a deployed controller. Full raw means, all five fixed candidates, all regions and failures are in the [generated report](report.md).

| Method | Mean failure-penalized RMSE (m) | Survival |
|---|---:|---:|
| LQR | 0.084356 | 108/108 |
| Best global fixed proposal: −0.04rad under gate | 0.083664 | 108/108 |
| Five-action privileged selector under actual gate | **0.082605** | **108/108** |
| Same finite selector with diagnostic gate bypass | 1.852602 | **18/108** |

The gated selector reduces full-episode error by **2.076% versus LQR** and **1.266% versus the best global fixed candidate**. Noise-seed reductions versus LQR are2.111%,2.013%,2.103%. It passes the predeclared practical1% diagnostic screen with preserved regional survival. Nominal reduction is3.806%; tire mismatch1.298%, low friction2.304%, sensor stress2.938%,20ms3.475%,100ms0% (stale fallback).

**Interpretation:** the existing bounded gate permits useful corrective behavior on these cases. Current learned proposals are not exhausting that demonstrated opportunity. This does not prove that learning alone is the only bottleneck or that a sensor-only student can recover the privileged result.

**Do not open the gates on this evidence.** The specific bypass policy failed90/108 episodes; the18 surviving cases are the severe-delay cases that still fall back to LQR. Its large mean is a failure-penalized score, not invented post-failure motion. Independent original-object replays reproduce representative failures and gated trajectories, with maximum state discrepancy below1.4e-15 in the eight checked cases. Bypass changes several supervisor restrictions at once; this does not identify an individual threshold or establish what every possible ungated controller could do.

The selected minimum is only over five held-proposal branches and200ms lookahead, re-planned at each worker submission. It does not search every action sequence or globally minimize episode error. The selector also sees true plant/state and the upcoming common sensor-noise realization. Therefore **2.076% is measured headroom for this privileged finite policy, not a theoretical/absolute maximum**. A low or negative result would likewise not prove that no better controller exists.

## What the next step can legitimately be

There is enough diagnostic signal to design a teacher/student experiment while retaining the current gate and physical bounds. Before training a student, define labels without relying on the actual future sensor-noise trace—for example expected-cost branches with independent training-only noise—and measure whether useful correction targets are predictable from the student's observed inputs/history. Keep train/development/test cases separate. This is a subsequent protocol, not part of Step1.

PPO already receives tracking/survival rewards every tick. Its sparse action-dependent signal should not be described as receiving no reward. No teacher training, distillation, new PPO run, native test, production gate change or model promotion occurred here.

## Verification and artifact semantics

- Six observer/gate/worker/branch/selection/baseline/bypass contract tests pass.
- 324 recorded LQR and±.08 fixed reference cells match the preceding development grid; maximum RMSE discrepancy6.38e-16m.
- 140,511 selected minima were checked in199,179 stored oracle trajectory rows.
- Eight original `Sensor`/`Execution`/plant object replays agree with the numerical kernel, including failed bypass cases.
- Active numerical source and frozen protocol are preserved in `source/`; raw oracle costs and trajectories are in the per-seed compressed traces.
- `branch_control_ticks` in episode CSVs is the **scheduled candidate-window budget** (`selector_calls ×5×20`), not a count of actually executed branch transitions. A branch that reaches a failure stops early and fills the remaining cost tail. No compute claim relies on that budget field.

These are three development noise repetitions on two known paths, not independent training seeds, held-out generalization or real-vehicle evidence. The historical controller/models/results remain unchanged.
