# ARIS audit remediation — 25 October 2026

This change addresses actionable findings from the [ARIS audit](../../EXPERIMENT_AUDIT.md) of source `966e034`. That report and its verdict are historical evidence and remain unchanged. Application fixes here are not a new independent ARIS acceptance or proof that AI outperforms LQR.

## Issue status

| Finding | Resolution | Evidence / remaining boundary |
|---|---|---|
| Unsupported fixed ablation means/SDs and final thesis tables | Retired both misleading generators with explicit migration messages. New `tools/controller_review/report.py` requires raw paired episode CSV, rejects duplicate/unpaired records and inconsistent failure penalties, and computes statistics across seed means. | A single seed reports no SD. No invented safety rating, latency result or causal-ablation claim is generated. The 504-row existing attribution grid was rendered successfully. |
| Missing-import auxiliary environments | Retired `BicycleEnv` and `LQREnv` explicitly instead of silently mapping incompatible state/action contracts. Their constructors explain the supported replacement. | Use `PathTrackingEnv` for full radian commands or `ResidualPathEnv` for normalized residuals. Old implementations/checkpoints are not compatible; historical source remains in Git. |
| Broken/ambiguous plotting | Replaced magnitude-based state guessing, unsupported path-generator arguments and synthetic fallback. Plot requires recorded reference and physical position, or an explicit NPZ state layout. Misaligned/nonfinite signals fail. | A recorded physical root trace was plotted successfully; displayed RMSE is over executed samples and does not replace survival/failure-tail scoring. Imports produce no figures or simulation. |
| Heuristic highway / proof video presented as learned or ISO evidence | Retired their executable/import-side-effect paths with explicit migration guidance. | Use actual policy bundles and documented native/surrogate workflows. No tanh heuristic is called PPO, and no ISO-compliance claim is generated. |
| Truncated jitter JSON | Original bytes moved intact to `historical/jitter_test_results.incomplete.txt`. Original JSON path is now a valid explicit incomplete-status record with no inferred metric. | Current active consumers must not treat the marker as experimental measurements. All 2,067 tracked JSON files parse. Historical audit counts still refer to their old commit. |
| Stale wiki | Landing page now points to existing experiments, current evidence and remediation. | Dated historical narratives are preserved. |
| Missing Revision5 evaluation adapter | Added `revision5/evaluate_execution.py`, which executes the exact `ExecutionEnv` used by training, including its 20 features, observed speed, pending/held actions, gate and reward. Legacy dimensions and missing/inconsistent checkpoint metadata fail before evaluation. | Commands, rewards, packet identity and severe-delay fallback match training at 0/10/20/100 ms in regression tests. This is a development training-distribution evaluator, not a new final or native test. |
| Learning attribution / confidence | Existing seven-candidate attribution evidence remains available; new report tool does not convert method labels into causal claims. New evaluation retains paired LQR comparison and one-seed uncertainty limits. | Superior new PPO performance is not established. Existing frozen experiments retain their negative results and stop rules. |
| Historical ZIP reproducibility | Added a nonexecuting package inspector and [machine-readable inventory](aris-remediation/archive-status.json); original ZIPs/manuscripts remain unchanged. [Reproduction status](../../research-inputs/REPRODUCTION_STATUS.md) names missing files and nonportable code. | **External blocker remains:** eight original manifest-listed files are absent, and candidate code references an unavailable external workspace. Exact historical reproduction cannot be completed from these inputs; no missing evidence was fabricated. Current repository workflows do not depend on executing that code. |
| Safety/stability/real-time and global superiority claims | Supported scope remains explicit in the current README, reports and generated tables. No timing-as-safety labels or blanket superiority outputs remain in the retired paths. | Finite simulation and small pilots cannot prove those claims. New formal/empirical evidence would be separate work, not a code correction. |

## Validation

**45 unit/contract tests passed:** new evidence/reporting/plotting tests 7, new evaluation parity tests 2, corrected root 6, revision4 5, revision5 execution 3 and robust gate 3, original research 5, frozen gate 6, action-range mapping 4, native adapter 4. The first attempted revision4 command used an absent filename; it was corrected to `test_contracts.py`, which executed all five tests successfully. No absent-file attempt is counted as a passing suite.

Additional functional checks:

- New report generator consumed all 504 historical attribution episodes and generated raw-derived tables with no fixed means/SDs.
- Existing 1,000-step **smoke** policy evaluated through the new adapter: 8/8 completed development episodes at one seed across 0/10/20/100 ms, 800 steps each. These are interface checks, not a performance-qualified policy. Its fresh zero-delay RMSE was slightly worse than LQR in this sampled case; no improvement claim follows.
- At 100 ms, the recorded smoke-policy and LQR scores are equal; regression checks compare actual commands and rewards, not only final means.
- Physical trace plotting ran headlessly and produced a figure with executed-sample RMSE 0.037056 m for the selected existing LQR case; no trajectory was synthesized.
- ZIP inspection found eight absent manifest members, no mismatches among present manifest-bound members, valid CRCs, and an external-path dependency in the candidate script. It does not execute embedded code or certify reproduction.

[Captured test outputs and summaries](aris-remediation/) are included. Preserved originals and historical model weights were not overwritten. No policy training, full-budget campaign, final reserved evaluation or native Webots campaign was launched by this fix.

## Supported commands

From repository root, activate the prepared Python 3.10 environment. For this cloud instance use `/workspace/lans-venv/bin/python`; set writable `NUMBA_CACHE_DIR` and `MPLCONFIGDIR` as needed. Each output directory/file must be new.

```bash
python tools/controller_review/report.py \
  --input integrations/webots/results/revision5-audit/episodes.csv --output /tmp/lans-recorded-table
python visualize_results.py \
  --input integrations/webots/results/controller-remediation/root-comparison/traces.csv \
  --method lqr --seed 101 --speed 25 --delay-ms 0 --output /tmp/lans-recorded-plot
python tools/controller_review/check_archives.py --output /tmp/lans-package-status.json
python integrations/webots/research/revision5/evaluate_execution.py \
  --policy integrations/webots/results/controller-remediation/execution-smoke/policy.zip \
  --seeds 101 --output /tmp/lans-execution-development
python tests/test_aris_remediation.py -v
python integrations/webots/research/revision5/test_evaluation.py -v
```

The execution evaluator expects the model's adjacent `complete.json` with matching step count, 20 observation components and 0.08-rad residual scale. Reward normalization was training-only; inference observations are the environment's fixed-scaled features. Loading a historical nine-feature policy directly fails.

## What cannot honestly be marked fixed

The exact uploaded historical reproduction package remains incomplete until the missing original material and its dependencies are supplied. The empirical goal of consistently stronger AI remains unproven. Predictor false accepts/rejects and the failed model-bank promotion remain measured limitations, not errors to hide or values to tune away. A new controlled, matched-budget pilot through the corrected execution interface is a separate experiment; five-seed full training remains paused until the development stop rules justify it.
