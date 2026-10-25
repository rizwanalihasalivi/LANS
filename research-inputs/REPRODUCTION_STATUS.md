# Original attachment reproduction status

These user-supplied source attachments are historical inputs, not a certified self-contained reproduction release. Their original bytes, original manifests and manuscript wording are retained unchanged. The current corrected code and results are linked from the repository README.

The nonexecuting check `python tools/controller_review/check_archives.py --output NEW_FILE.json` lists missing manifest entries and external paths. The captured [inventory](../docs/research/aris-remediation/archive-status.json) shows:

| Package | Status |
|---|---|
| Supplementary ZIP | ZIP CRC passes and present manifest-bound members match, but eight original listed files are absent. |
| Submission candidate ZIP | ZIP CRC passes; reproduction source references `/mnt/data/lans_work`, which is not supplied as a portable workspace. No complete runnable reproduction was established. |

Missing supplement members, under `LANS_JSA_Supplementary/`:

- `REFERENCE_AUDIT.csv`
- `REFERENCE_AUDIT.md`
- `REVIEWER_EVIDENCE_STATUS.csv`
- `REVISION_STATUS.md`
- `references.json`
- `revision_analysis_source.py`
- `rewrite_complete.py`
- `verify_equations.py`

Do not fill these with invented data, rewrite an original manifest to hide missing inputs, or execute embedded code as a workaround. Exact historical reproduction requires the missing originals and the code/data expected by its external workspace. The preserved audit extractions are text inspection aids, not replacement original artifacts. Current development uses the repository's corrected workflows, which are separate from these packages.
