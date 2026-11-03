# Nonlinear predictive-plan correction

[Executed results, evidence and remaining gates](RESULTS.md). Use this version
for the repaired integrated Python pipeline; the historical default
`integrations.unified_lans` entry point continues to reproduce the older version.

V4 fixes the reported corridor failures. Its remaining statistical gain target
requires a separate, frozen improvement; it cannot be achieved by relabeling a
0.55% gain as 1% or changing a confidence threshold.

The linear predictive planner assumes constant speed while the supervisor may
command substantial braking. V5 projects and refines its proposal using the
same nonlinear bicycle integration, actual bounded longitudinal intervention,
steering rate, angle and residual-fusion constraints as application. A declared
two-sweep/four-block finite search also considers the legal baseline plan when
the stricter linear QP cannot find a feasible seed. Solver failures remain
logged; they are not reported as successful QP solves.

Nominal optimized, adaptive-only and hybrid modes all receive this repair. The
same three 32,768-step policies are reused with zero additional learning. This
is a model/planning correction, not evidence of new PPO training success. The
adaptive-only reference remains visible, and equal compute or pure-PPO
superiority is not assumed.

Fresh development uses a new initialization namespace and phase 9 / amplitude
1.15; reserved cases use a separate namespace and phase 21 / amplitude 1.25.
All original numeric gates, failure penalties and physical limits are retained.
Reserved cases stay unopened if prerequisites fail. Real-worker and Webots
validation must use the same final implementation and pass their own checks.

```bash
cd /workspace/LANS
# For a new Python 3.10 virtual environment, install requirements.txt here.
# The recorded /workspace/lans-venv environment is already installed.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba
/workspace/lans-venv/bin/python -m tools.unified_control_v5.campaign --stage all
```

The effective protocol, source hashes, cached episode data and replay audits are
stored in `results/corridor-v5/confirmation-campaign/`. Calibration and v4 failure
results remain intact. Hardware/vehicle-model assumptions and statistical
limitations of the earlier finite grids still apply.

For an actual asynchronous-worker functional check with the same controller:

```bash
/workspace/lans-venv/bin/python -m tools.unified_control_v5.live \
  --policy results/python-campaign-v2/policies/seed-42 \
  --scenario following --output results/corridor-v5/new-live-check
```

Output directories must be new. `--network ego_blackout` and `--fault crash`
exercise the sensor-loss and worker-failure paths. The three recorded live
checks are engineering diagnostics; they do not replace the unopened formal
multi-actor wall-clock gate or the final native Webots campaign.
