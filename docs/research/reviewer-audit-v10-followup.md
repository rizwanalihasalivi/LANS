# Supplemental audit and strict 20% target checks

The frozen diagnostic retains its original source snapshots and raw outcomes. A supplemental checker closes two audit gaps without rerunning or selecting episodes:

- The diagnostic manifest included prior source inputs but did not directly hash all v9 output actor files used as current inputs. `check_target20.py` now verifies all six offline actors and three runtime actors against the immutable v9 evidence seal stored in git commit `5f80922`. Exact model hashes are recorded in `reviewer-audit-v10-target20.json`.
- The diagnostic boolean did not include the nominal-degradation and per-pair guards. The stricter checker evaluates those guards, exact matched case/noise keys, survival, heading/rate limits and the 20% threshold against each available comparator. It also explicitly blocks a full all-baseline claim because both fixed controls and a matched robust published vehicle baseline/MPC are absent from this narrow new-numerics grid. The diagnostic already failed; these corrections do not change the outcome or relax criteria. The initial supplemental record is preserved separately.

Eight additional contracts pass: exact 20% floating-point boundary, subthreshold gain rejection, nominal-regression masking, survival masking, unmatched grids, boolean request IDs, boolean observation timestamps and valid runtime-response parity. Together with the 36 core contracts, 44 checks passed. These are regression/contract checks, not 44 independent driving trials or proof of global correctness.

The new-runtime miss occurred at seed802 CPU stress tick27: release lateness 10.341163ms, current control processing 0.531179ms and thread CPU 0.527796ms. Optional admission was skipped and LQR fallback remained correct. The original10ms deadline was already missed at release. Prior-cycle post-commit work, timer wakeup and host scheduling cannot be separated with the recorded fields, so a unique root cause is not established. Cgroup throttling counters did not change during this timing campaign. This is not a justification to forgive or remove the miss.

Run the research environment's single resumable command:

```bash
python tools/controller_review/run_ppo20_audit.py --publish
```

It checks the frozen audit pipeline and supplemental source-model/target evidence before optional publication. Exit2 keeps the unmet full20% claim visible. The current result is **not20%**: corrected PPO gains0.379% vsLQR, is0.159% worse than the student, and1.126% worse than the causal planner on the diagnostic. No new retraining was run: the predeclared causal-planner headroom screen failed. That screen is a finite heuristic, not a proof that every possible PPO or architecture cannot reach20%. Further authority/objective/preview/representation changes need a justified new finite experiment and strong matched controls; reserved data remain unopened.
