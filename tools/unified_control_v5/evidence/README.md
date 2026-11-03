# Sealed Python repair evidence

Extract the ZIPs at the repository root; members retain their `results/...`
paths. Existing files should be identical before extraction. The reader
`python -m tools.unified_control_v5.verify_evidence` verifies outer SHA256,
ZIP CRC, safe unique member paths, sizes and every member SHA256 without
third-party packages. Add `--campaigns` in the pinned research environment to
recompute both campaigns' raw physical traces, failures, RMSE and original
statistical decisions after extraction.

- `training-calibration-and-probes.zip`: all training-only controller/horizon
  calibration and intermediate development diagnostics, with source snapshots.
- `v4-confirmation.zip`: the first complete repair campaign, including its
  failed promotion gate, full raw trajectories and protocol/source freeze.
- `v5-confirmation.zip`: the final nonlinear repair campaign, including its
  failed promotion gate, full raw trajectories and protocol/source freeze.
- `live-diagnostics-and-logs.zip`: actual-worker traces and exact source bytes,
  including the initial summary-serialization exception, corrected attempt,
  and complete terminal logs from the executed repair studies/tests.

`EVIDENCE_MANIFEST.json` inside each archive lists all other members. The outer
hashes are in `SHA256SUMS`. No passwords, environment dumps, caches or virtual
environments are included. No saved failing experiment was deleted.

Exact original policies, earlier v2/v3 results and their snapshots remain in
[`python-results-v2-v3.zip`](../../unified_improvement/evidence/python-results-v2-v3.zip).
The extracted `results/python-campaign-v2/policies/seed-{42,43,44}` folders must
match the model digests in each confirmation protocol. The original regression
case lists are recovered from the same earlier archive. Calibration freezes
predate later code changes; use their own snapshots for historic reproduction.

Physical replay verification relies on the unchanged bicycle plant. Controller
admission/model fitting and the heuristic uncertainty estimate are unit-tested
and recorded; archive integrity alone is not a proof of safety or significance.
