# ARIS audit evidence package

Read the [project audit summary](../../../EXPERIMENT_AUDIT.md), [unmodified substantive reviewer response](reviewer-report.md) and [coverage ledger](coverage.md).

The reviewed source is `966e034a2868ce122855d86417ecbe67ec1b1120`. Only audit documents, scripts and captured outputs are added here. Controller code, historical results and models were not changed. The full raw response retains its original file paths and UTC date; the summary uses Asia/Shanghai time.

## Preserved outputs

- `evidence/census-summary.json`, `census-details.json`, `source-duplicates.json`, and `native-metric-checks.json`: completed earlier census and stored-telemetry checks.
- `evidence/legacy/diagnostics.json`: completed corrected-root probes.
- `evidence/rev45-test*.txt`: completed revision4/5 contract test outputs.
- `evidence/completion-check-results.json`: fresh completion-review grid checks.
- `evidence/completion-provenance-output.txt`: completion-review checkpoint/provenance checks.
- `trace/`: route, exact initial/retry/completion prompts, follow-up requests, failure records and final completion metadata. No full substantive verdict existed for the usage-limited earlier attempts. Partial child sessions were not recovered as independent completed reviews.

## Scripts and limits

Scripts in `evidence/` are preserved audit instruments, not application code. Read them before execution: they retain their original `/workspace/LANS` and `/workspace/lans-aris-audit` paths, and some write diagnostic outputs. Their presence does not establish that they completed. In particular, `rev123-diagnostics.py` and `rev45_check.py` lacked completed output JSONs and their assertions are not counted as passed. Use the completed output files and coverage ledger for actual outcomes.

The exact completed commands and source paths are recorded in the coverage document. Reproduction needs the prepared Python 3.10 environment with NumPy/SciPy, CPU PyTorch, SB3 and Numba. No manuscript reproduction code, model retraining or new native Webots campaign was executed as part of the completed review. The 5,200-file inventory belongs to the reviewed commit; these added audit files are intentionally outside that count.

ARIS is a workflow, not a separate model. Native fresh-agent review here is same-family/provisional. Requested `gpt-6-astra`/`ultra` is recorded separately from unknown independently reported model identity. Full source and binary correctness, citations, physical safety, worst-case timing and all archived claims are not certified by this report.
