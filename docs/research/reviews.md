# Review findings from supplied research artifacts

Reviews performed before this checkpoint were document/source inspection and CSV consistency checks. Supplied reproduction scripts were not run. These findings describe the uploaded historical packages, not new LANS experiments. Original files and hashes are preserved in `research-inputs/`.

## Original manuscript

The original design uses LQR plus PPO residual correction and a latency-adaptive gain. Full-command weighted fusion and an explicit symbolic supervisor are proposed changes requiring new implementation, training and validation.

Claims requiring correction or additional evidence include:
- Mean latency about 203 microseconds and p99 about 550 microseconds do not establish worst-case execution time.
- A 100 Hz PPO update frequency does not establish 10 ms inference duration; a derived 49x speedup needs matched measurements.
- Claims beyond 200 ms jitter need evidence beyond the stated tested range.
- CPU measurements versus a GPU's rated 350 W TDP do not establish a fair 305x energy advantage.
- Stability claims need assumptions applicable to delay, saturation, switching and nonlinear dynamics; empirical tracking alone is insufficient.
- Reported RMSE improvement (0.199 versus 0.236), mass robustness and other historical results must be linked to reconstructable evidence before reuse.
- References and Tesla parameter attribution remain subject to primary-source verification.

## LANS_JSA_Supplementary_Package (2)(4).zip

Manifest inspection found 390 entries: 382 present with matching sizes/hashes and eight missing artifacts: REFERENCE_AUDIT.csv, REFERENCE_AUDIT.md, REVIEWER_EVIDENCE_STATUS.csv, REVISION_STATUS.md, references.json, revision_analysis_source.py, rewrite_complete.py, verify_equations.py.

The reviewed `sources/episodes.csv` contains 1,218 rows. Selected aggregate checks:

| Method | Survived / episodes | Reported aggregate RMSE checked |
|---|---|---|
| Full | 120 / 126 | 0.206001 |
| Zero residual | 40 / 42 | 0.206999 |
| No fallback | 123 / 126 | 0.198365 |
| MPC | 38 / 42 | 0.229674 |

Across the combined physical-cell comparison, LANS had 426 survivors in 441 executions and MPC 142 in 147 (both 96.5986%). Ordinary RMSE favored MPC (0.176712 versus 0.179498); the penalized metric favored LANS (0.212889 versus 0.225458). Metric definitions and denominators matter; these results do not justify blanket superiority.

C-port paired checks covered 63 pairs with matching survival and maximum trajectory difference approximately 2.98e-7. This supports the packaged comparison, not a hard real-time guarantee. WCET linkage had 40 unresolved symbols. Proof claims remain conditional. Some reward-on/off and standalone policy artifacts were missing; reproduction paths did not match the package layout.

## LANS_JSA_Submission_Candidate_Package.zip

The candidate contains 14 files, including a byte-identical copy of the original supplementary ZIP. Its additional CSV contains 252 episodes (42 per method):

| Method | Survived / episodes | Aggregate RMSE checked |
|---|---|---|
| Full | 40 / 42 | 0.2063775 |
| Observer-matched MPC | 40 / 42 | 0.1524562 |
| Original MPC | 38 / 42 | 0.2296737 |
| No arrival correction | 35 / 42 | 0.2805559 |
| No lead compensation | 36 / 42 | 0.252715 |
| Neither observer component | 32 / 42 | 0.3274155 |

Independent CSV aggregation matched supplied values. Original parity differences were approximately 9.53e-8 for full LANS and 1e-16 for MPC. The candidate appropriately acknowledges the stronger observer-matched MPC and the approximately 1.76 g demand of the 25 m/s lane-change case.

Remaining packaging issues: three manifest Python paths omit their `reproduction/` prefix despite matching file hashes; reproduction references hardcoded `/mnt/data/lans_work`, a shared library and an incomplete gymnasium shim layout; pandas is needed beyond stated NumPy/SciPy requirements. Claimed additional 324-case sweeps, 27 replays and training reconstruction were not identifiable as complete reproducible artifacts in the inspected package. The original eight missing files remain missing.

These are useful post-hoc single-policy analyses, not multi-seed general performance validation. Preserve them as historical evidence and rerun fair comparisons under the new protocol rather than treating them as new-architecture results.
