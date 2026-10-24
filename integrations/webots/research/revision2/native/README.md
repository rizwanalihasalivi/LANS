# Frozen revision-2 gate in native Webots

This is native transfer of the exact performance gate and learned policies from commit `14ab389`. No gate, weight, reward, policy, estimator or LQR retuning is performed. The native protocol and working interface were committed as `65099e1b73385e68b347f42b20ba92dacc902a83` before reserved native runs began. Previous surrogate/native campaigns remain unchanged.

## What runs

The native grid has 270 independent Webots process launches: five existing trained policy seeds × speeds 15/20/25 m/s × six scenarios × LQR/gated residual/gated full-command. All cases use the previously calibrated native vehicle and DLC220 path, 1 ms physics, 10 ms control and 10 s acceleration warmup. The initial lateral path offset is approximately zero, as in the previous native campaign; this differs from the surrogate's deliberate 0.15 m initial offset. Sine-path transfer is not included.

The gate is imported directly from `research/revision2/gating.py`, with the verified development freeze `{horizon_steps: 20, relative_margin: 0.01}`. Residual clipping, candidate weights, cost, freshness, persistence and ramp rules are unchanged. The runtime receives the same common noisy Kalman estimate, local map curvature and nominal scheduled speed. Its actuator input is the existing mean front-wheel angle proxy. It never receives hidden contact/friction changes. Both learned modes use the unchanged `PolicyWorker` in a separate CPU process; control polls and submits without waiting, with one job in flight and drops while busy. Startup readiness and predictor compilation complete before physical warmup/testing.

Scenarios are nominal, native contact softening, friction 0.6, doubled sensor noise plus 10 ms measurement delay, 20 ms added minimum inference availability delay and 100 ms added minimum delay. Contact softening divides front/rear calibrated force-dependent slip by 0.65. This is a native-contact mismatch proxy, **not** a measured 35% reduction in cornering stiffness or an exact Fiala equivalent. No contact recalibration is selected from reserved results.

Each method in a matched cell uses the same new noise seed, physical random seed 42, warmup, generated world and duration. Native noise base 1910000 is disjoint from previous streams. Two native processes run concurrently, each with private Xvfb and XDG directories; existing shared Webots installations are untouched. Real worker scheduling makes learned-control runs conditional on cloud timing. Actual output age, dropped requests and wall timings are logged; added delay is a minimum simulation delay, not a guarantee of the final age. No real-time deadline claim is made.

## Reproduce

From the checkout root, use the existing private installation; see the parent research README if dependencies are absent:

```bash
bash integrations/webots/install-private.sh
bash integrations/webots/install-research.sh
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR="$PWD/integrations/webots/.runtime/numba"
export MPLCONFIGDIR="$PWD/integrations/webots/.runtime/mpl"

"$LANS_PYTHON" integrations/webots/research/revision2/test_gate.py -v
"$LANS_PYTHON" integrations/webots/research/revision2/native/run.py smoke \
  --output "$PWD/integrations/webots/results/native-smoke-local"
"$LANS_PYTHON" integrations/webots/research/revision2/native/analyze.py \
  --output "$PWD/integrations/webots/results/native-smoke-local"
"$LANS_PYTHON" integrations/webots/research/revision2/native/run.py reserved \
  --output "$PWD/integrations/webots/results/native-reserved-local"
"$LANS_PYTHON" integrations/webots/research/revision2/native/analyze.py \
  --output "$PWD/integrations/webots/results/native-reserved-local"
```

The original launches used `/workspace/lans-setup/venv/bin/python` for the runner/analyzer; the runner defaults to the pinned private `research-venv` interpreter for Webots controllers and workers. They used canonical output names `revision2-native-smoke` and `revision2-native-test`. Every launch records the actual controller interpreter path and elapsed wall time. The driver logs its world-derived mass/CG/inertia audit. Source snapshots, configuration, generated world, raw CSV, console/Xvfb logs, per-case metrics, hashes and complete grid summaries are retained. Existing output directories are rejected; partial results are not silently retried or overwritten.

The three smoke cases use a separate seed and only establish interface execution. The unchanged gate contract tests already verify nominal surrogate parity and acceptance/fallback behavior. The native analyzer independently reads every CSV, recomputes error metrics, checks the full unique case grid, source/policy/freeze hashes, simulation clocks, angle/rate limits, earned-cost margin, worker age and availability. Missing prediction costs use zero placeholders accompanied by `prediction_available=0`; they are not measured zero costs.

For 100 ms cases, the analyzer checks zero learned weight and equality to the local LQR command at every tick, then compares the complete physical/control traces to each paired LQR run. Exact equality is reported separately from any nonzero numerical differences, which remain in `verification.json`. Worker timing fields are excluded from physical equality because LQR launches no worker.

## Statistical interpretation

Gated residual remains the primary comparison; gated full-command is a predeclared secondary comparison. Each of five paired seed differences averages the three speeds within one region. Report all six regions, survival and penalized RMSE (2.5 m fill for an unexecuted failed tail). Descriptive t(4) intervals are not multiplicity-adjusted inference. Nominal preservation permits ≤2% mean RMSE increase without survival loss. Consistent improvement requires all five paired seed means negative and no survival decrease; clear advantage additionally requires ≥5% mean reduction. Do not replace this primary result with whichever secondary result looks strongest.

[Native results](../../../results/revision2-native-test/report.md) and [verification](../../../results/revision2-native-test/verification.json) contain the actual outcome. These results concern the known DLC220 course and unchanged five policies; they cannot establish unseen-path generalization, physical tire equivalence, formal stability, real-vehicle safety or broad superiority. Future changes require another development revision and new reserved data.

## Recorded outcome

All **270/270** reserved native runs survived. Gated residual reduced regional mean RMSE by 1.29% nominal, 0.21% contact softening, 1.31% low friction, 0.97% sensor stress and 0.91% at 20 ms, with all five paired seed means improving in each region. The 30 severe-delay gated trajectories exactly matched their paired LQR physical/control traces with zero learned authority. Nominal preservation passed; no region met the ≥5% clear-advantage criterion. Absolute primary mean improvements are only about 0.35–1.15 mm.

Gated full-command transfer was mixed: mean regressions of 0.20% under contact softening and 0.34% under sensor stress are retained, alongside its improvements elsewhere. The experiment does not establish broad architecture superiority. Actual asynchronous output schedules depend on cloud timing, while severe-delay LQR equality was directly verified. No post-test retuning was performed.
