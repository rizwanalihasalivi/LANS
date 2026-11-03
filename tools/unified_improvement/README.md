# One declared architecture repair after longer Python trials

[Executed results and limitations](RESULTS.md) records both complete campaigns,
all gate failures and the conditional Webots status. The linked verified archive
contains both raw datasets, exact trained policies, original source snapshots,
repair scripts, and failure/retry logs. Its per-member manifest and outer checksum
support integrity checks; current tracked documentation includes final handover
links added after the archive's source snapshot.

The v2 campaign is preserved and completes without parameter changes. Its longer
merge trials reveal a concrete failure: the simple proportional residual and
learned branch can both be rejected while LQR leaves the tracking corridor. The
stronger finite optimized-deterministic comparator survives the same recorded
case. The opening report proposes an optimized deterministic branch; this repair
actually includes that grid in hybrid candidate selection.

This is a new version, **not** a correction applied to old episode files. It
reuses the exact same three 32,768-step PPO endpoints: no extra training, seed
selection, authority increase, new reward or model retuning. It keeps every
numerical promotion threshold from v2, including the 5% LQR and 1% optimized-
reference targets. A gain from adding deterministic search is not attributed
to PPO learning. The hybrid has one additional PPO proposal relative to the
optimized-only comparator; equal online compute is not claimed.

Fresh development uses independent initialization seeds, phase 6 / amplitude 1.1;
reserved cases use a separate seed namespace, phase 17 / amplitude 1.2. The v2
reserved data remain unopened unless the original v2 gate passes. The same
320-episode development and 96-episode communication stress plan applies.
The development dimensions still share analytic route families and are not
broad real-road generalization evidence.

```bash
cd /workspace/LANS
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
/workspace/lans-venv/bin/python -m tools.unified_improvement.run_python --version 3 \
  --training results/python-campaign-v2 --output results/python-improvement-v3
```

All source, policy and protocol hashes are sealed before any v3 outcome. The
adapter configures the shared campaign library only inside its own process;
the v2 scripts and results remain unchanged. Passing performance gates is still
not a timing guarantee. Actual spawned-worker confirmation must pass before any
native Webots transfer. If a gate fails, retain it rather than change the target
or run Webots under a different controller.

The first v2 auditor stopped after all 320 development episodes because its
module omitted `Command` and `math` imports. The supported launcher supplies those
existing types to the auditor and continues cached-stage verification. For a
completed run, `python -m tools.unified_improvement.verify --version 2 --output
results/python-campaign-v2` or the equivalent `--version 3` command audits and
continues the required stress stage. Original failure logs and frozen source
remain preserved; no raw episode, tolerance, formula or promotion threshold is
changed. The full auditor test also corrupts a trace and confirms rejection.
