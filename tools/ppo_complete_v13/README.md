# V13 fixed-policy completion pipeline

This research continuation keeps the shared safety repair separate from the
incremental benefit of PPO. Every learned policy uses the same repaired owner,
original physical/quality/freshness guards, and matched references. The
registered10% goal is a test, never a presumed result. No thesis drafts, figures
or presentation tables are produced.

The training protocol specifies three independent65536-step PPO endpoints,
their initial BC controls and update-matched continued-BC controls. Run the
post-learning pipeline from the repository root with the prepared environment:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba-ppo-complete-v13-cli
/workspace/lans-venv/bin/python -u -m tools.ppo_complete_v13.campaign --resume
```

The stages are continued BC,864 validation episodes,1728 final episodes,
independent Python audits,180 actual-runtime episodes,120 representative
physical Webots episodes, qualification, final independent audit and bounded
byte-preserving evidence archives. Native execution uses the installedR2025a
and Xvfb wrapper; managed sandbox execution may need local display IPC access.
The runtime/native phases must have the host free of concurrent numerical
training or audits. Every timing miss and actual safety failure remains.

`--from-stage final` or another named stage continues from a completed prior
stage. `--resume` validates existing complete evidence and consumes it without
rerunning measured missions. Partial/failed attempt logs are preserved and
require inspection; the pipeline does not delete them or select a favorable
timing rerun. A failed performance threshold remains failed even when every
numerical audit passes. The full qualification record distinguishes mean10%
from a95% confidence lower bound of10%.

Results live in `results/ppo-complete-v13`; retained execution logs live in
`/workspace/cloud-setup`. Sealed archives live under `evidence/`. Verification
and restoration use:

```bash
/workspace/lans-venv/bin/python -m tools.ppo_complete_v13.package --verify
/workspace/lans-venv/bin/python -m tools.ppo_complete_v13.package --restore /tmp/lans-v13-restored
```

Use a separate NumPy/Numba cache ending in `-tests` for pytest; the canonical
CLI package and pytest's short module alias must not share compiled caches.
Historical v11/v12 fixture dependencies must be restored separately as pinned
in the protocols. The native campaign covers24 predetermined final fixtures,
not all144 final fixtures or hardware outside the Webots surrogate.
