# Isolated predictor and objective development ablation

This revision follows the full-project audit and the user's request to test a more discriminating gate before spending on further training. The [protocol](protocol.json) is committed before research outcomes. All previous models, protocols, source snapshots and results are preserved.

Three gate variants share the same plant, sensors, LQR, action bounds, age rejection, worker lifecycle, persistence and weight ramp:

- **Legacy:** original gate and combined cost, called verbatim.
- **Preview only:** original nominal linear model and cost, with evolving curvature from the same three preview channels already available to the student. This changes geometry prediction; it does not provide hidden tire parameters.
- **Lateral objective only:** original constant-curvature model, with only its existing lateral stage and terminal cost terms retained.

Each gate receives constant −0.04 rad, constant +0.04 rad, and the same frozen supervised student. Pure LQR is the common reference. Three student/noise pairs × three speeds × two known paths × six conditions × ten methods produce **1,080 fresh development episodes**. This is a controlled gate ablation, not a retrained-policy comparison or reproduction of a published competing algorithm.

Use the original revision8/9 every-available-worker inference cadence. New requests retain their real observation timestamps. The recent revision10/11 slow-query diagnostics used a different cadence and their headline numbers are not copied into this comparison.

The protocol separates **gate progress**, **additional learned benefit**, and the **5% regional research target**. A revised gate must improve current-gate student error by at least 1%, improve all three paired seed means and at least two predefined stress regions, preserve nominal tracking/survival/fallback, and demonstrate benefit beyond both same-gate constants before it is eligible. Results alone never trigger weight or horizon changes.

Only an eligible gate proceeds to an independent, gate-matched teacher headroom check. Only a passing teacher check permits two 100k PPO pilots, followed by a separately frozen fresh-noise evaluation. A failed screen stops that path and leaves reserved noise unused. This conditional sequence avoids treating a better gate or a privileged teacher as proof that new PPO training will help. It does not authorize full-budget training.

Use the pinned research environment from `tools/cloud/README.md`, a new output directory, and one BLAS thread per worker. Model/normalizer hashes, source commit, noise IDs, raw episode metrics and representative traces accompany the run. From repository root:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-v12-numba MPLCONFIGDIR=/tmp/lans-v12-mpl
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision12/test_gate12.py -v
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision12/test_report12.py -v
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision12/run12.py --output /tmp/lans-v12-development
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision12/report12.py --run /tmp/lans-v12-development
```

The runner requires committed research sources and snapshots their hashes before starting three isolated single-thread shards. It opens only the development split. Report validation checks the full paired grid, failure penalties, physical bounds, and per-cell exact severe-delay trajectory equality before any conditional promotion decision.
