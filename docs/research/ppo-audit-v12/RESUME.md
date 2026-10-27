# PPO performance audit v12

User request: investigate why PPO misses the 20% matched-baseline target, fix reproducible defects, and save resumable progress. Starting evidence: commit 79e4433, v11 training and 840-episode comparison. Historical evidence remains immutable.

## Progress

- [x] Read repository instructions and locate active training, sensing, queue, supervisor, plant, export and evaluation dependencies.
- [x] Reproduce numerical/interface/checkpoint defects and add independent contract tests.
- [x] Quantify authority, delayed credit and action exploration on all frozen v11 new-PPO episodes.
- [x] Implement versioned fixes; verify unchanged baseline, freshness and causal-input contracts.
- [ ] Run a finite, recorded matched diagnostic; report improvements and regressions without weakening the 20% target.
- [ ] Publish source, diagnostics, tests and exact resume command; commit/push completed milestones.

No controller is promoted. Reserved tests remain unopened. Neither laptop timing nor vehicle validation can be inferred from this software audit.

## Resume

Repository: `/workspace/LANS`; branch: `reports/opening-report-2026-10-26`.
Python: `/workspace/lans-venv/bin/python` (Python 3.10).
Resume command: `/workspace/lans-venv/bin/python tools/reviewer_v12/run12.py --publish`.

Read `status.json` and `protocol.json` for current stage and the frozen budget. Two arms x three seeds x50,000 new steps are declared. RK4 response forecasting replaces legacy Euler; an explicitly experimental exploration arm divides initial action-head logits by4 and resets only that head's Adam slots. All safety/selection rules and baselines are retained.

Training saves immutable atomic10k-step checkpoints containing PPO/Adam, full vector environment, queue, observer, reward normalization and accumulated returns, counters and Python/NumPy/Torch RNG. A unit test spanning an automatic episode reset requires exact equality to uninterrupted training. Completed episodes are saved individually. Corrupt or source-incompatible state is refused. A kill may require replaying work since the latest complete checkpoint; no partial update is treated as complete.

Current stage: initial9new contracts and24independent numerical checks pass; full regressions and finite experiment are next. No new training launched yet. Historical source files and reserved data remain unchanged.
