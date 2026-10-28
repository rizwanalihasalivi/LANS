# Recovered PPO v13 experiment complete

Read README.md for findings and failed/passed criteria.

Resume/check: `python tools/reviewer_v13/run13.py --publish`

Full exact training state saved every10k steps. Six final100k endpoints only; no automatic extra training. Each completed episode has a verified trace hash. `--verify-only` checks sealed evidence; `--replay` repeats raw checks. Reserved evaluation unchanged.
