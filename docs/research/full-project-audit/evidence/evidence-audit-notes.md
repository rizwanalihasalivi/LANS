# Whole-project evidence and claim audit notes

Audited baseline commit: `5c3a55da1e8f1bd4398ad906405f210b82203103` (merge of latest main into audit branch). Read-only audit: no repository source, model or raw result was modified by this agent. Outputs: `/tmp/evidence-census.json`, `/tmp/evidence-metrics.json`, this file. Other agents are concurrently implementing source fixes; the census describes the tracked baseline, not all later untracked test additions.

## Coverage actually performed

- 6,421 tracked paths inventoried.
- 1,293 tracked Python files, 165 distinct byte contents; 176 classified active by excluding `results`, `research-inputs`, `historical`, and historical ARIS evidence directories. This is a declared path classification, not a claim that all 176 were semantically inspected.
- All 1,293 tracked Python files parse as Python syntax (BOM-aware), zero syntax errors. This is not runtime coverage.
- All 2,218 tracked JSON files parse, including a strict check rejecting NaN/Infinity constants; zero errors.
- 1,339 CSV/CSV.gz files streamed; 1,117,845 data rows; zero row-width/parsing errors and zero nonfinite/negative `penalized_rmse` values. SB3 Monitor's first JSON comment line is skipped before CSV parsing (an initial naive parser incorrectly treated its commas as CSV; corrected census supersedes that attempt).
- Local Markdown links inspected in root README, `docs/research` excluding historical full ARIS reviewer evidence, and active `integrations/webots/research` docs: zero missing relative targets. External URLs and anchors are not checked.
- Independently recomputed complete raw episode means/survival for revision8 (540 rows), revision9 (756), revision10 (72), revision11 (8). All published headline numbers match their stored rows. No training, native run or final-test-based selection was performed.
- Read current main README, existing ARIS audit/remediation, revision8/9 methods/outcomes/drift, revision10/11 reports and source protocols; inspected historical package reproduction status.

## Findings / changes primary should make

1. **No new raw-number fabrication or arithmetic discrepancy found in current r8–r11 headline tables.** Preserve those raw historical rows. Matching numbers alone does not certify implementation semantics.
2. **Known revision10/11 timestamp defect supersedes their semantic conclusions.** Simulation audit agent found that the 50ms query workflows refreshed held proposal timestamps every10ms. They are correcting submission semantics and arranging separate corrected reruns. My raw-table agreement for these revisions is only historical arithmetic consistency, not a clearance of those controller semantics. Add prominent supersession pointers in current docs/report navigation and do not overwrite old evidence.
3. **Current navigation has historically dated status text.** `docs/research/README.md:3,11` describes the initial handoff as “proposed, not implemented” and new experiments as future; its heading is explicitly24October historical, so not an evidence-integrity defect. A short present-status pointer would prevent readers mistaking it for current status. Likewise current branch README should link the whole-project audit and corrected latest diagnostics; leave frozen r8/r9 reports' stage-end stop statements historically intact.
4. **Historical reproduction blocker remains external.** `research-inputs/REPRODUCTION_STATUS.md:9-23` lists eight absent original supplement files and unavailable `/mnt/data/lans_work` dependencies. These cannot be repaired by inventing evidence. Current code works separately; do not mark full historical repository reproduction solved.
5. Minor renderer defect: active `revision11/report.py` emitted headings without space (`##200ms`, `##Objective`, `##Interpretation`). Simulation agent has already fixed current generator; historical results can stay frozen with a link to corrected evidence.

## What the raw evidence says about2% versus5–10%

Exact recomputations (mean penalized episode RMSE):

| Revision | LQR | Student | Teacher / relevant comparator |
|---|---:|---:|---:|
| r8 |0.0844343735989|0.0826121504055|teacher0.0825510389448|
| r9 |0.0843067663750|0.0825634899290|finetune100k0.0828299852378|

- r8 student improvement2.158153%; teacher2.230531%; teacher improves over student only about0.074%. This teacher is a finite five-action,200ms,three-forecast approximation with privileged current truth, not a global upper bound (`revision8/protocol.json:4-7`). Near-teacher student accuracy does not prove all controller headroom is exhausted.
- r9 student improvement2.067778%;100k fine-tuning1.751676%. All finetune development-selected steps are0. The endpoint does not improve its initialization. `revision9/protocol.json:10-12` explicitly uses per-update targetKL0.01 with no teacher loss/imitation replay. The retained actor-drift report shows decreasing student agreement and increased teacher regret; that is evidence of drift, not proof that it alone caused tracking degradation.
- **Severe-delay dilution is too small to explain the5% gap.** On r8, excluding latency100 raises student gain from2.158153% to2.461245%; teacher2.230531% to2.543787%. Do not present excluding fallback cells as attaining5% or silently change the primary metric.
- **Tire mismatch dominates absolute aggregate error.** r8 tire-region LQR mean0.1753432243 versus roughly0.06–0.08 elsewhere; it contributes34.611343% of the sum of six regional LQR means. Student tire gain is only1.513%, so improving already-good nominal tracking alone has limited leverage on the aggregate.
- Descriptive arithmetic only: if all five other current student regional means stayed exactly fixed, tire-region improvement versus LQR would need9.723863% to yield5% overall, and24.169994% to yield10% overall. This is a mathematical explanation of the target's size, **not a prescribed final-test-tuned objective or a prediction of feasibility**.
- The nominal/student gate/physics constraints, objective mismatch and weak PPO credit are plausible mechanisms requiring controlled ablations. Do not call any one “the proven cause of the2% ceiling” from these data.
- Newly discovered implementation defects should be fixed and checked before causal claims; no current evidence guarantees that these fixes themselves will yield5–10%.

## Research limits that are not software bugs

- Three optimization/noise pairs, known geometries/condition families: neither broad generalization nor statistically strong superiority to MPC/native deployment is established.
- Fixed failure-tail2.5m scoring is declared; raw RMSE is not self-normalized to a method's output maximum. Reward normalization is separate from evaluation metric.
- r8 privileged teacher extra data/budget versus prior PPO is disclosed, not equal-budget causal comparison (`revision8/protocol.json:13`). r9 scratch and finetune share additional RL budget but finetune also has supervised pretraining (`revision9/protocol.json:11`).
- Revised diagnostics use correlated shadow states and offline privileged future noise, not deployable performance or failure probabilities. With the timestamp issue now corrected, reruns must be read before repeating old exact diagnostic counts as current findings.

## Suggested concise project-level conclusion

“Current recorded supervised hybrid gains are modest and internally consistent; PPO fine-tuning did not add benefit. This audit found implementation defects that require corrected diagnostics, but there is no evidence that the present2% result is one fix away from5–10%. The strongest remaining research question is whether a predictor/objective change improves the high-error mismatch region while preserving nominal tracking, survival and fallback on a separately frozen experiment.”
