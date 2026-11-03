# Python-first results — 3 November 2026

[Complete raw/source/model bundle](evidence/python-results-v2-v3.zip) ·
[Checksums](evidence/SHA256SUMS) ·
[Unified comparison figure](evidence/unified_python_results.png) ·
[Completed risk-study figure](evidence/completed_risk_results.png)

**The declared Python campaign is complete. The Webots promotion gate is not
passed.** All outcomes are retained; no reserved or native case was opened after
a failed prerequisite. These are finite simulation studies, not a claim that all
future thesis experiments or physical validation are complete.

## Completed checks and computation

- **197 Python unit tests passed**, plus the real-worker functional check.
  This includes the root/integration, active v12, risk semantics, adapter and 24
  historical controller/report/lifecycle scripts. The final additional audit
  test executes full trace replay and deliberately corrupts a trace to confirm
  rejection. Initial missing OSQP and test-fixture issues were resolved with
  original failure/retry logs retained; no assertion was relaxed.
- **32 independent integrator comparisons passed** against separately coded
  DOP853 equations; maximum state difference approximately **4.373×10⁻⁷**.
  This verifies numerical consistency, not real-vehicle model accuracy.
- **98,304 new PPO training steps:** three seeds, exactly 32,768 steps each.
  All final weights, hashes, software versions and periodic checkpoints exist.
- **832 new development/stress episodes, 85,742 audited control ticks** across
  v2 and the one separately declared v3 improvement. Mirrored/model/actor cases
  are correlated; these totals are not independent traffic replicates.
- No additional learning, architecture search, best-seed selection or changed
  threshold was used after v2. V3 reuses all three exact final v2 policies.

## Matched development outcomes

Each grid has 32 scenario/mirror/speed/stiffness cells; PPO and hybrid include
all three actors. V3 uses fresh seeds and changed route phase/scale, so v2-to-v3
differences are not a same-population causal effect estimate.

| Outcome | V2 simple-residual hybrid | V3 optimized-branch hybrid |
|---|---:|---:|
| LQR-relative mean tracking gain | +0.844% | **+29.713%** |
| 95% cluster-bootstrap gain interval | [-15.045%, +9.511%] | **[+2.005%, +62.639%]** |
| Gain relative to optimized deterministic reference | -80.273% | **-3.572%** |
| Hybrid mean penalized RMSE | 0.666103 m | **0.438075 m** |
| Matched optimized-reference mean RMSE | 0.369497 m | **0.422965 m** |
| Hybrid corridor/failure cases | 37/96 | **19/96** |
| Hybrid observed collision episodes | 0/96 | 0/96 |
| Communication-stress hybrid corridor/failures | 31/72 | **14/72** |
| Communication-stress hybrid observed collisions | 0/72 | 0/72 |

V3 per-actor LQR-relative gains are **24.862%, 32.146%, 32.131%**. Thus a
substantial tracking gain is observed against this LQR implementation on the
fresh grid, but this does not make the controller safe or superior to the
stronger deterministic reference. The LQR itself fails 9/32 v3 cells; the
optimized reference fails 6/32. Reference weakness and incomplete survival must
remain visible when interpreting the large relative gain. Failure-penalized
RMSE includes missing ticks after early termination; stopping early cannot earn
an artificially low score.

The v3 optimized reference is approximately **3.57% better in RMSE** than hybrid
on the declared mean comparison. No PPO-specific superiority is established.
The hybrid has an additional PPO candidate and does not claim equal online
compute. New policies were not passed to final real-worker confirmation because
the earlier performance/safety gate failed.

## Why Webots remains closed

The predeclared targets require a positive balanced gain, at least 1% over the
optimized reference, no hybrid safety/corridor failures and acceptable progress,
heading/rate and timing behavior. The observed 29.7% LQR-relative gain alone does
not satisfy these requirements. Reserved tests, final real-worker timing and
native Webots are **NOT_RUN**, rather than silently marked passed.

The next useful development work is constraint-aware baseline/selection tuning
and reliable stopping/recovery under missing ego/traffic observations. Failures
cluster in following, merging and curved tracking, with ego loss among the stress
failures. A nominal linear sampled-data eigenvalue check remains stable; the
present evidence does not establish one unique cause such as sample-rate alone.
Blind PPO budget extensions, gate removal or more residual authority are not
supported remedies. Any new design requires a new declared development stage
and untouched confirmation data.

## Historical LANS-RISK completion

The separate approved dense-Merge continuation is complete: **231 original +
33 amended = 264 conditions / 13,200 episodes**. This task computed only the
remaining **29 batches / 1,450 episodes**, preserving the four previously saved
amended batches and all original results. Main confirmation (44,000), observation
delay (4,000) and development (4,800) remain audited: **66,000 total saved episode
records** across those historical stages. The original unamended robustness
stage alone is still 231/264; the initialization amendment is disclosed.

Dense-Merge LANS records show zero observed collisions and 100% task completion
at 0/500/1000 ms command delay, but corridor completion is **100%/96%/40%**.
Matched nominal MPC has identical binary endpoints and lower mean RMSE in these
cells. These are useful positive safety/task observations with an explicit
tracking limit, not universal superiority, equivalence or a certified risk bound.

## Evidence and verification repairs

`results/python-campaign-v2/` and `results/python-improvement-v3/` retain protocols,
source snapshots, raw ticks, summaries, bootstrap gates, model hashes and audits.
The frozen auditor omitted `Command` and `math` imports; explicit repair launchers
supplied those imports without changing raw data, formulas, tolerances or gates.
Original exception logs and repaired-verification records are preserved.

Use the supported `tools.unified_improvement.run_python` launcher for reproduction.
Archived v2 source remains frozen for provenance. The final results bundle
contains both campaign directories and all failure/retry logs, not only favorable
episodes. The historical risk completion is retained separately in the
LANS-RISK repository under `python_campaign_20261103/`.
