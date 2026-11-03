# Executed integration validation

3 November 2026. This records a new integrated simulation implementation; no
historical LANS/LANS-RISK experiment was rerun or used as a new result.

## Implementation and checks

- `python -m pytest tests integrations/unified_lans/tests -q --disable-warnings`:
  **54 passed** (28 existing root checks and 26 new checks).
- New checks cover bicycle integration, low-speed braking, actuator limits,
  source/sequence rejection, delayed command application, applied-history and
  FIFO forecasting, TTC and crossing occupancy, age uncertainty, missing traffic,
  stale ego, application-time and wall-time proposal expiry, dead-worker fallback,
  historical-policy incompatibility, zero-residual/LQR parity and full-loop
  multi-vehicle execution.
- Deterministic calibration evaluated the declared 12 gain pairs on 12 fixed
  nominal development states per pair. Selected lateral-error gain **0.04**,
  heading-error gain **0.0**. This is a finite local search, not global optimality.
- Three sealed PPO bundles completed **2,048 steps each**, seeds **42/43/44**.
  They have the new 17-feature contract, policy hashes and saved training source.
  These budgets demonstrate training/loading integration, not controller
  convergence, superiority or final scientific confirmation. A prior unsealed
  integration pass is preserved separately and was not used to select a winner.

## Real asynchronous full-loop suite

Executed command from `/workspace/LANS`:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl \
/workspace/lans-venv/bin/python -m integrations.unified_lans run \
  --suite --compare --seconds 3 \
  --policy results/unified-v1/sealed-policies/seed-42 \
  --calibration results/unified-v1/calibration.json \
  --output results/unified-v1/validation
/workspace/lans-venv/bin/python -m integrations.unified_lans.verify \
  results/unified-v1/validation
```

Five modes (LQR, fixed, deterministic, PPO, hybrid) × 12 cases, each three seconds:

| Case | What was exercised |
|---|---|
| Following | Timestamped lead-vehicle information and longitudinal intervention |
| Merge | Lane-change reference, neighboring vehicle and common-cost selection |
| Crossing | Route-ray occupancy and TTC-based risk supervision |
| Curved | Shared bicycle control on a sinusoidal route |
| Delay | Delayed traffic packets plus 100 ms physical command FIFO |
| Loss | 30% synthetic neighbor-packet loss |
| Reordering | Alternating delayed/current neighbor packets |
| Traffic blackout | Neighbor packets stop after one second |
| Ego blackout | Ego packets stop after one second |
| Worker stall | Each inference response is delayed 300 ms |
| Worker crash | Owned inference worker is terminated after one second |
| Model mismatch | Plant cornering stiffness is 80% of the predictor's |

**Results:** all **60/60** requested intervals completed, **3,600 ticks**, zero
recorded collisions and zero corridor exceedances. PPO responses were actually
accepted **1,141** times and PPO commands selected **224** ticks across PPO/hybrid
modes. Deterministic commands were selected **813** ticks. Thus inference was
exercised rather than silently replaced by a dummy action throughout.

Both stall cases accepted **zero** late responses and rejected **eight** each.
Crash cases continued after the worker died. The raw audit verifies fallback
constraints rather than treating mere process survival as sufficient.

**Timing:** **one** controller tick exceeded the configured **50 ms** budget.
The largest per-case control p95 was approximately **22.573 ms**. These timings
cover the recorded controller decision, not a certified sensor-to-actuator WCET
or a guarantee for the old 10 ms requirement. Functional checks pass; strict
zero-deadline-miss acceptance does not pass this run.

**Replay:** raw hashes, FIFO ordering, angle/rate/acceleration bounds, missing-data
and dead-worker fallback, PPO source/wall age, physical transitions, per-tick
tracking and clearance, and summary RMSE all pass: **60 episodes / 3,600 ticks**.
The execution provenance matches the current integration source hashes.

The seed-43 and seed-44 sealed bundles were also loaded in real spawned workers
and each completed an additional 60-tick following episode with passing replay
audit. Both accepted 59 real responses. Seed 43 selected PPO on nine ticks;
seed 44 selected deterministic correction throughout, an honest selection result
rather than a failed inference path. Across these checks and the main suite,
**62 short episodes / 3,720 ticks** were audited. This is not a three-seed full
scientific comparison.

## Retained evidence and limits

`results/unified-v1/validation/` contains `provenance.json`, `summary.json`,
`audit.json` and per-case `ticks.jsonl`/`summary.json`. The raw records retain
states, issued/applied controls, neighbor truth, source timestamps, freshness,
risk states, critical vehicle, candidate costs, clearance, steering rate and
jerk. Warning metrics explicitly use a current-truth constant-velocity hazard
proxy, not future collision ground truth. Frames and episodes are correlated;
these totals are not independent policy/traffic replicates.

This establishes that the architecture runs as one simulation pipeline under
the tested faults. It does not finish held-out scientific evaluation, native
Webots transfer, physical testing, formal safety/stability, or the separate
historical dense-Merge amendment. Existing results and models are preserved.
