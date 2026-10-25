# Step1 — finite-grid privileged headroom diagnostic

The environment was ready and this diagnostic runs now; no multi-day infrastructure wait or neural training is needed. The experiment examines the proposed residuals **−0.08, −0.04, 0, +0.04, +0.08 rad** under actual execution constraints.

**It does not compute an absolute/theoretical maximum improvement.** Five candidate values, a200ms hold-candidate lookahead and greedy receding selection restrict the policy class. The local minimum window error need not minimize full-episode RMSE, and a small gain does not prove that gate authority alone is limiting. Even this oracle may lose to a fixed policy over an episode.

## Frozen design

[Protocol](protocol.json) and numerical source/report implementation were committed as `3750347` before the full evaluation. Previous controller sources, gains, checkpoints and results stay frozen. This task stops after Step1; no teacher/student/PPO training or production gate change is launched.

At every **available worker submission**, clone physical state, Kalman state/covariance, delayed raw measurement, gate persistence/weight/sequence, held packet and pending job. Roll each candidate forward20 control ticks, repeatedly proposing that same residual whenever the worker becomes available. Recompute sensing, measured-speed LQR, the actual gate and nonlinear actuator/plant every branch tick. Select the lowest sum of true squared lateral error, apply only one real10ms transition, and repeat at the next submission. Pending jobs cannot be overwritten. Ties prefer zero/smaller magnitude, then the declared candidate order.

All candidate branches use the same upcoming sensor-noise draws. The selector therefore has **current truth, true plant parameters and future-noise privilege**. The gate itself gets only the estimated state/measured channels. This is an intentionally privileged evaluation diagnostic, not a deployable controller or a ready teacher-label dataset. A later teacher design must remove or explicitly investigate future-noise leakage and partial-observation ambiguity.

## Comparisons

Eight methods × three noise repetitions × three speeds × two known paths × six regions = **864 episodes**:

- Unchanged LQR.
- Each of the five fixed proposals under the unchanged gate.
- The privileged selector under that same gate.
- A diagnostic-only selector bypassing performance/envelope/persistence/weight restrictions, retaining the bounded proposal, full-command limits, physical lag/rate limits, one-job worker and age≥50ms fallback.

Bypass removes several restrictions together; its result cannot identify a specific threshold or justify deployment. These are noise repetitions, not trained-model replicas. The grid deliberately reuses revision6 development noise so LQR and±.08 fixed results can be checked against prior records. No reserved noise or native simulator is involved.

All full-episode scores include2.5m failed tails. Every method and failed case remains in the report. Every oracle trace retains five window costs and the selected minimum. No horizon/candidate/threshold tuning follows the outcome. A1% spending screen is a practical diagnostic rule, not a theoretical or statistical boundary.

PPO receives tracking/survival reward each tick. Gate acceptance of only2–3% means action-dependent learning feedback is sparse, not that all reward is absent. This experiment tests available correction behavior; it cannot prove student learnability.

## Reproduce and inspect

Use the pinned Python3.10 research runtime (`/workspace/lans-venv/bin/python` in this cloud instance), NumPy1.23.5/Numba0.57.1. Three single-thread CPU processes execute independent noise-seed shards. Numerical kernels are checked against the original Sensor, Gate, Execution, physical transitions and stored baselines before use.

```bash
cd /workspace/LANS
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/workspace/lans-v7-numba
export MPLCONFIGDIR=/workspace/lans-setup/matplotlib
python integrations/webots/research/revision7/test_oracle.py -v
# Choose a new output directory; preserve existing evidence.
python integrations/webots/research/revision7/run.py --output /tmp/lans-oracle-step1
python integrations/webots/research/revision7/report.py --run /tmp/lans-oracle-step1
```

Canonical outputs: [report](../../results/revision7-headroom/report.md), [decision](../../results/revision7-headroom/decision.json), [episodes](../../results/revision7-headroom/episodes.csv), and per-seed compressed oracle traces. These links become available when the frozen run and verification complete.

Trace reason codes:0 missing,1 age,2 sequence,3 envelope,4 predicted cost,5 persistence,6 earned,7 nonfinite,8 invalid prediction,9 diagnostic bypass,10 local LQR. Window costs are sums of squared lateral error, not full-episode RMSE. Cost of a new zero proposal may still include a previously held/pending nonzero packet; the worker state is never reset to manufacture a better branch.
