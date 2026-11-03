# Raw experiment evidence

No thesis drafts, figures or presentation tables are included. Archives contain
raw trajectories, machine-readable results, protocol/source snapshots, provenance,
audits and terminal logs. Calibration search results and failed gates remain.

`SHA256SUMS` records each outer digest. `EVIDENCE_MANIFEST.json` inside each ZIP
records the size and SHA256 of every other member. Extract at the repository root
to restore canonical paths; refuse conflicting existing files.

The functional/execution archive also records the parallel-work manifest. Its
alias index points byte-identical intermediate files to already archived canonical
members. Differing intermediate bytes remain as separate members. Verification
checks every alias against the actual archived member digest and size. Duplicate
intermediates are not counted as additional episodes or independent samples.

Use `python -m tools.unified_control_v6.verify_archives` for standard-library archive
integrity checks and `python -m tools.unified_control_v6.verify` in the pinned
research environment for read-only physical/metric/selection verification.
