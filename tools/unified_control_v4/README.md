# Constraint-aware corridor and sensor-loss repair

This version preserves the older failed studies and fixes the shared control
foundation. It does not change corridor width (1.75 m), collision geometry,
steering/acceleration limits, freshness thresholds, failure penalties, test cases
or the original 5%/1% statistical promotion rules.

## Repairs

- A finite training-only search over LQR penalties 1/4/16/64 and 64 cases per
  candidate selected R=16 under a fixed safety/progress/balanced-cost rule. R=1
  failed 22/64, R=4 failed 2/64, and R=16/64 each passed 64/64; R=16 had the best
  eligible balanced cost. Every comparator receives that same calibration.
- Predictive eligibility now checks the lane corridor as well as vehicle
  clearance. The compiled predictor is numerically checked against Python
  dynamics and cost, not substituted with a different easier plant.
- A causal discrete-model observer estimates tire stiffness from successive
  validated ego packets and the command actually applied between them. It
  never receives the fixture's true stiffness. Feedback and prediction use the
  same estimate. An off-grid 0.83 parameter test checks recovery independently
  of the benchmark's 0.8/1.2 values.
- Candidate admission checks multiple model hypotheses and predicted heading/
  rate budgets. Identified uncertainty is an engineering noise-floor heuristic
  for this full-state simulation, not a calibrated statistical safety bound.
- Ego information older than 0.2 s cannot enter PPO. During a bounded 2.5 s
  stopping window, steering is reconstructed from the last original packet and
  actual command history while maximum bounded braking is issued. Source time
  is never refreshed. History gaps or expiration use the explicit held-steering
  fallback; no missing measurement is invented. This assumes the declared
  braking dynamics and is not a physical safety certificate.
- Optimized, adaptive-only and hybrid comparators all receive the same nominal
  constrained predictive planner and candidate grid. The adaptive-only ablation
  is retained to distinguish model adaptation from a PPO contribution.

A second declared training-only calibration compared 0.25/0.5/1.0 s horizons
without using a learned policy or confirmation data; all candidates were safe
on that grid, and 1.0 s won the fixed balanced-cost rule. Limits are unchanged.

## Executed v4 results

`results/corridor-v4/confirmation-campaign/` retains the sealed protocol, source,
raw records and audits. Original development cases pass **96/96 hybrid runs**;
original communication stress passes **72/72**. Fresh development and stress
also have zero hybrid corridor failures/collisions. The formal v4 campaign
contains 752 episodes, 90,240 audited ticks.

The fresh hybrid mean RMSE is 0.078252 m versus calibrated LQR 0.081720 m and
optimized nominal reference 0.078686 m: gains **4.244%** and **0.552%**. These fix
the earlier mean-ranking reversal, but the unchanged 5%/1% confidence gate still
fails. The 95% interval against optimized reference includes zero. No reserved
or native result is claimed from v4.

## Reproduce

```bash
cd /workspace/LANS
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba
/workspace/lans-venv/bin/python -m pytest tests integrations/unified_lans/tests \
  tools/unified_campaign/test_campaign.py tools/unified_improvement/test_verify.py \
  tools/unified_control_v4/test_control.py -q
/workspace/lans-venv/bin/python -m tools.unified_control_v4.campaign --stage all
```

Calibration source bytes are stored separately and checked against their
pre-run digests. Generated outputs are not overwritten; new controller source
requires a new run directory. The older frozen v2/v3 readers should be run with
their archived source snapshots, not by disabling hash checks against new code.
No new training, seed selection or favorable-case deletion is performed.
