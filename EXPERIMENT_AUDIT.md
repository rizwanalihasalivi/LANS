# ARIS project audit — 25 October 2026

**Historical verdict below.** Subsequent [remediation status and validation](docs/research/aris-remediation.md) address the actionable code/reporting findings and document the original-package and research-evidence limits. The original audit verdict is not rewritten as an independent re-review.

**Reviewed source:** `966e034a2868ce122855d86417ecbe67ec1b1120` (PR #8).

**Overall verdict: FAIL for unrestricted repository-wide evidence acceptance. Current isolated research: WARN.** This distinction matters: the reviewer found current research comparisons internally consistent, with small conditional gains; it did not find those results fabricated. The repository-wide failure concerns unsupported executable result tables, malformed historical evidence and incomplete reproduction packages. It is not a finding of intentional misconduct.

ARIS `research-review` and `experiment-audit` were used from pinned upstream commit `23745b69a14880b5716d1773e5d20f5f1e6ab1d6`. The completed review used fresh native session `/root/aris_audit_completion`, requested `gpt-6-astra` / `ultra`. Actual model identity was not separately returned. **Review independence: same-family; acceptance: provisional**, not a Claude/Gemini or cross-family endorsement. Two earlier attempts hit usage limits; completed diagnostics were retained, and uncompleted assertions were not counted as passes.

[Full reviewer report](docs/research/aris-audit-2026-10-25/reviewer-report.md) · [Coverage and limitations](docs/research/aris-audit-2026-10-25/coverage.md) · [Evidence and reproduction notes](docs/research/aris-audit-2026-10-25/README.md)

## Audit chart

| Check | Verdict | Reviewer conclusion |
|---|---|---|
| A. Reference / ground truth | PASS in inspected active paths | Geometric reference is independent of policy; actual simulated motion is propagated. |
| B. Metric normalization | PASS in inspected active metrics | Raw RMSE and fixed failure-tail scoring are consistent; training reward normalization is not presented as evaluation accuracy. |
| C. Result existence / provenance | FAIL repository-wide | Current checked comparisons agree with records, but fixed unsupported root tables, truncated JSON and incomplete supplied packages remain. |
| D. Dead / miswired code | WARN | Active metrics are wired; auxiliary environments and visualization paths still have reproducible defects. |
| E. Scope / claims | WARN | Small simulation gains are supportable; general superiority, safety, stability and real-time claims exceed the evidence. |
| F. Evaluation type | PASS classification | Driving evidence is simulation-only; computer timing measurements are separate from physical-vehicle validation. |

## What changed since the earlier review

| Topic | Current conclusion |
|---|---|
| Root false-motion plant and double LQR | Repaired in the corrected demonstration; historical results are not retroactively validated. |
| Observation normalization, previews, speed and LR handling | Corrected paths and saved parity/contract probes support the fixes. |
| Revision3 range-only / 600k route | No useful consistent learning trend; failed progress screen. |
| Revision4 gate-aware / reward / randomized pilots | Implemented experiments are real, but all new arms failed their extension screen; combined arm D does not isolate randomization. |
| Revision5 execution interface | Better alignment of command execution, history and measured speed; only a 1,000-step smoke model, not trained-policy performance evidence. |
| Revision5 nonlinear model bank | Real diagnostic with mixed results; failed promotion. |
| Why LQR stays strong | Strong scheduled/feedforward/estimated-state baseline, little remaining error, low learned authority, historical execution mismatch and no demonstrated superior new policy. These are mechanisms/confounds, not a proven single cause. |

## Remaining actionable findings

| Priority | Finding | Action supported by the review |
|---|---|---|
| High | `ablation_study_real.py` calls fixed means/SDs “actual experimental results”; `thesis_summary_table.py` can generate a final table from fixed fallback values. | Retire these scientific-output paths or require identified raw inputs; label historical illustrations explicitly. |
| High | Hybrid-versus-LQR does not isolate the learning contribution. | Include predeclared nonlearned candidates under the same gate and matched budgets. |
| High | Old checkpoints were not trained with the new revision5 execution/history interface. | First verify the evaluation adapter, then consider a small controlled pilot; do not claim the smoke model solves tracking. |
| Medium | Predicted gate improvement can disagree with realized short-horizon cost. | Preserve the reported false-accept/reject diagnostics; do not interpret gate acceptance as safety. |
| Medium | Auxiliary modules have missing imports; a visualization call uses an unsupported argument; `jitter_test_results.json` is truncated. | Fix or explicitly retire these separate paths without invalidating sound research data. |
| Medium | Supplied packages have missing manifest entries / external path dependencies; original manuscript overclaims remain historical. | Qualify completeness and claims; preserve originals and document what is actually reproducible. |

The review's latest development attribution table is especially useful:

| Candidate under the same frozen gate | Mean penalized RMSE (m) | Improvement versus LQR |
|---|---:|---:|
| LQR / zero | 0.084253436 | 0% |
| Legacy 1M PPO | 0.082702470 | 1.841% |
| New A100k PPO | 0.083820524 | 0.514% |
| Constant +0.08 rad | 0.083757088 | 0.589% |
| Constant −0.08 rad | 0.083613992 | 0.759% |

These are 72-cell development means per candidate. Legacy PPO beats the tested constants; the new A100k policy does not. Different training budgets/seeds prevent an equal-budget causal conclusion. Learning contributes something in the tested legacy comparison, but greater new-policy benefit is not established.

## Evidence and next decision

- All 5,200 tracked paths inventoried; 981 Python files represent 111 distinct contents. This is not a claim of exhaustive semantic reading.
- 764 CSV/CSV.gz files were streamed in the preserved census; 350 native metric/telemetry pairs recomputed without mismatches.
- Completion reviewer checked 4,236 recorded episode rows, recomputed 3,966 failure-penalized scores and checked 32 checkpoint metadata/provenance records.
- Saved corrected-root and revision4/5 contract outputs were inspected; full native simulations and training were not rerun.
- The full report and coverage explicitly state unread/unverified material, historical limitations and unexecuted diagnostics.

**Recommendation: keep the five-seed full-training campaign paused.** First clean up unsupported outputs and verify the intended revision5 evaluation adapter. Any subsequent pilot should isolate one hypothesis, preserve strong LQR, use matched budgets and nonlearned controls, and demonstrate reproducible benefit before spending on full training/native validation. No fixes or new training were performed by this audit.

The retained full reviewer report uses its UTC date (24 October); this cover uses the user timezone, Asia/Shanghai (25 October). Report publication does not change the reviewed source commit or constitute a new environment snapshot.
