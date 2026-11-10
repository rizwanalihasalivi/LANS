# V2V audit evidence — 4–5 November 2026

Source, raw inputs, control and native motion traces, replay and independent
scores for all 81 new 70-second runs are preserved. All 81 passed; 40 use
fresh validation seeds. This is a regression cohort, not a real-world or
universal safety proof. Comparative benchmarking remains on hold.

The root is `results/v2v-audit-20261104-v1`. Its `source/` is the original
115-file campaign snapshot. `post-campaign-verification-source/` separately
records the later archive-verifier fix; the trial source plan was not rewritten.
Includes 221-test results, regression failure evidence, 1-D/2-D SMT checks,
six fresh continuous 2-D certificates, a development certificate, 128 historical
native refinement rechecks, malformed-byte stress and both unreachable-range
diagnostics (ordinary recovery failures with expected braking).

Copy every ZIP, `SHA256SUMS` and `inventory.json` to one directory. Verify
with the current hardened verifier before extracting into a NEW directory:

```bash
python -m integrations.connected_v2v.settling.package verify --output integrations/connected_v2v/evidence/audit-20261104 --extract /workspace/lans-setup/audit-extracted-new
```

The final old-archive integrity recheck is retained as the separate sidecar
`historical-archive-verification.txt`; it is not part of the new raw campaign.
New-archive integrity and isolated frozen-source replay reports are sidecars.

| Archive | Bytes | Members |
|---|---:|---:|
| audit-001.zip | 31138772 | 124 |
| audit-002.zip | 28883110 | 88 |
| audit-003.zip | 30278793 | 114 |
| audit-004.zip | 29851355 | 112 |
| audit-005.zip | 29664125 | 97 |
| audit-006.zip | 29730662 | 107 |
| audit-007.zip | 28584884 | 93 |
| audit-008.zip | 19696567 | 147 |
| audit-009.zip | 16707998 | 121 |
| audit-010.zip | 12533700 | 215 |
