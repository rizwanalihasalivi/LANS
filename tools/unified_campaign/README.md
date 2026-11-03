# Python-first validation campaign v2

User goal: strong, reproducible Python results before transferring the same frozen
controller to Webots. Failed outcomes remain part of the evidence. The numerical
thresholds below are declared engineering promotion criteria, not promised gains
or certified safety bounds.

## Frozen sequence

1. Verify active Python contracts and the relevant historical controller tests.
2. Train three fresh PPO endpoints at seeds 42/43/44 for exactly 32,768 steps each
   (98,304 new steps). Use the existing 32×32 network, PPO settings and actual
   gated/physical-FIFO transition reward. Source and protocol hashes are sealed
   before training. Periodic policy/optimizer checkpoints are retained; exact
   interrupted environment/RNG continuation is not claimed.
3. Run 32 matched development cells: four traffic scenarios, mirrored routes,
   two speeds (8/16 m/s) and two stiffness values (0.8/1.2), six seconds per
   episode. The lateral/heading initial perturbations use separate development
   seeds. LQR, fixed correction, the finite-calibrated deterministic correction,
   a stronger five-value optimized deterministic search, PPO and hybrid are
   retained. Baselines are shared across the three actors rather than counted
   as extra independent samples. Total: 320 development episodes.
4. Independently exercise 24 communication/command-delay stress cells with LQR
   and all three final hybrid actors: delayed packets, loss, out-of-order packets,
   traffic blackout, ego blackout and 100 ms command FIFO, across four scenarios.
   Total: 96 stress episodes. These are logical-time fault trials, not runtime
   measurements. No weak case is removed.
5. Only after development and stress pass may 32 disjoint, phase/scale-perturbed
   reserved cases be evaluated. No checkpoint/seed selection or post-result
   threshold changes are permitted.
6. Real spawned-worker wall-clock confirmation and native Webots transfer remain
   conditional on all preceding Python performance and integrity gates. Python
   measurements must never be copied into a Webots table.

## Promotion gate

All three final hybrid actors are included. Require at least 5% mean RMSE gain
against LQR and 1% against the stronger optimized deterministic reference, with
positive lower 95% bootstrap gain intervals; each actor must improve over LQR.
Limit mean heading and steering-rate increases to 10%, preserve at least 99% of
matched LQR progress per cell, and permit no hybrid collision/corridor failure.
Bootstrap averages actors and correlated mirror/stiffness variants inside eight
scenario/speed clusters before resampling 5,000 times. This small-cluster interval
is diagnostic and does not establish universal generalization. Raw episode
length, failures, progress and control authority remain visible. Early-ended
episodes receive missing-tick tracking penalties and cannot earn an apparently
better RMSE by colliding early.

Strict final runtime acceptance requires zero observed misses against the
declared period as well as valid fallback/freshness. This does not imply WCET.
The simulator's 50 ms loop does not validate a separate 10 ms hardware target.

## Why logical time is explicit

The initial integration reused wall time inside candidate lifetime prediction.
That is appropriate for real asynchronous execution, but makes a fast scientific
trial depend on machine scheduling. `Pipeline` now accepts an optional clock;
default real-time behavior remains unchanged. This campaign injects a deterministic
clock and models one in-flight response with exactly 50 ms service. Synchronous
training still differs from asynchronous inference and is documented as such.
Real inference timing is measured separately. Current controller source hashes
will differ from the preserved v1 evidence snapshot for this explicit reason.

The research harness also supplies the same explicit target speed to all methods;
it does not artificially slow the candidate to claim tracking gains. Optimized
deterministic search is disclosed as an extra comparator, not relabeled as PPO.

## Reproduce

From the existing `/workspace/LANS` checkout, use the LANS Python 3.10 environment:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba
/workspace/lans-venv/bin/python -m pytest tests integrations/unified_lans/tests \
  tools/unified_campaign/test_campaign.py -q
/workspace/lans-venv/bin/python -m tools.unified_improvement.run_python --version 2 \
  --output results/python-campaign-v2
```

Use a NEW output directory for a new protocol/version. Existing verified episodes
are cached, but a partial training folder is deliberately not silently retrained
or treated as an exact resume. The complete scripts, parameters and seeds are
stored under `source/` and `protocol.json`; changing a hashed source blocks reuse.
Stage summaries, gates and raw per-tick JSONL files remain under the run directory.
The runner will stop before reserved/Webots stages when a prerequisite fails.

Extended historical MPC tests additionally need the repository pin
`osqp==0.6.3` from
`integrations/webots/research/revision6/requirements-mpc.txt`; retain the existing
NumPy 1.23.5 / SciPy 1.10.1 pins when installing it. No new secrets, paid resources
or model APIs are needed. Historical LANS-RISK amendment computation uses its
separate Python 3.12 environment and frozen runner; those results must be
reported separately from this integrated bicycle pipeline.

The frozen original runner is preserved for provenance. Its first audit found
two omitted imports (`Command`, `math`); the supported launcher above supplies
those imports to the verifier without changing recorded episodes, tolerances or
selection rules. Original failure/retry logs remain in the evidence bundle.
