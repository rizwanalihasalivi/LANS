# Completed v12 audit

Read README.md and semantic-review.md for outcomes and limitations. No controller is promoted; reserved tests remain unopened.

Preferred cloud command: `/workspace/lans-venv/bin/python tools/controller_review/resume_ppo_audit12.py --publish`

This checks the pinned software, serializes guarded runs, restores verified checkpoints and completed episodes, uses the corrected typed verifier and preserves failed trials. Add `--verify-only` for hash verification. The finite300k-step budget is exhausted; no extra training starts.
