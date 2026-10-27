# PPO performance audit v12

User request: investigate why PPO misses the 20% matched-baseline target, fix reproducible defects, and save resumable progress. Starting evidence: commit 79e4433, v11 training and 840-episode comparison. Historical evidence remains immutable.

## Progress

- [x] Read repository instructions and locate active training, sensing, queue, supervisor, plant, export and evaluation dependencies.
- [ ] Reproduce numerical/interface/checkpoint defects and add independent contract tests.
- [ ] Quantify authority, delayed credit, action exploration, reward components and available controller headroom on development data.
- [ ] Implement versioned fixes; verify unchanged baseline, freshness and causal-input contracts.
- [ ] Run a finite, recorded matched diagnostic; report improvements and regressions without weakening the 20% target.
- [ ] Publish source, diagnostics, tests and exact resume command; commit/push completed milestones.

No controller is promoted. Reserved tests remain unopened. Neither laptop timing nor vehicle validation can be inferred from this software audit.

## Resume

Repository: `/workspace/LANS`; branch: `reports/opening-report-2026-10-26`.
Python: `/workspace/lans-venv/bin/python` (Python 3.10).
Read this file and the versioned audit source before continuing. The previous v11 runner cannot resume interrupted training: it deliberately rejects partial folders. This audit will add checked checkpoint/resume support rather than deleting or silently restarting partial runs.

Current stage: semantic inspection and defect reproduction. No new training launched yet.
