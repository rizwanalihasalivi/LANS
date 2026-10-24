# LQR-default performance-gated development revision

This revision follows the user's new architecture direction without editing the specification or the previous campaign. Existing full-command and residual policies (five seeds, one million steps each) remain frozen. There is **no new PPO training**. The revision evaluates a model-based gate on the isolated Fiala surrogate; previous native Webots results must not be relabeled as tests of this new controller.

## Controller

LQR is the exact default. The learned command must pass validity, sequence, age (<50 ms), state-envelope and predicted-performance checks. Missing, rejected or stale packets select LQR explicitly and immediately set weight to zero. Accepted candidates need three consecutive qualifying control ticks. Weight increases by at most 0.05 per 10 ms tick; rejection removes authority immediately.

For a full-command policy, the candidate is its clipped complete steering command. For a residual policy, first form `candidate = clip(LQR + clip(residual, -0.08, 0.08), -0.5, 0.5)`. Then use the same formula for both roles:

```
command = (1 - weight) * LQR + weight * candidate
```

Candidate weight limits are 0.1, 0.25 and 0.5, each scaled by freshness (full through 10 ms, zero at 50 ms) and limited by the ramp. The gate evaluates **the actual ramp-limited fused command**, not an unexecuted raw PPO command. It selects the lowest predicted cost only if improvement exceeds both the development-selected relative margin and an absolute 1e-7 floor. No default 0.7 learned weight remains in either gated method; `old_fusion` retains it solely as a frozen comparator.

The predictor uses a nominal linear bicycle with the common R=100 LQR gain, estimated lateral/heading/velocity/yaw state, measured actuator and local map curvature. It simulates explicit 0.05 s actuator lag and 0.35 rad/s rate limits at 10 ms Euler steps. Candidate command is held for the first 50 ms; LQR continuation is used thereafter. Integrated cost weights are `(ey/0.5)^2 + 0.2*(heading_error/0.1)^2 + 0.01*((yaw_rate-v*curvature)/0.2)^2 + 0.001*(command/0.5)^2`; terminal position/heading cost has multiplier 0.1. The horizon assumes constant local curvature and speed. It does not receive hidden plant friction/stiffness, true lateral velocity or future noise. Predicted improvement is not a realized-performance guarantee.

## Split and freeze

`protocol.json` was written before development and defines all scenarios, candidates, selection rules and test criteria. Development uses two existing policy seeds, speeds 15/25 m/s, one known sine path and six scenarios: 96 episodes across LQR plus three candidate residual gates. Test uses five policy seeds, speeds 15/20/25 m/s, two known paths, all six scenarios and five methods: **900 episodes**. Noise seeds have separate bases 310000 and 910000. Policies and path geometries are reused; only noise streams are newly held out.

Development selects the lowest penalized RMSE subject to no aggregate survival loss and ≤2% nominal RMSE degradation. All three candidates qualified. The selected 20-step horizon / 1% margin was frozen in commit `c966bb26a190be288c38efffc0498ac2c11f63ac` before reserved evaluation started. `freeze.json` records all rankings, protocol, source and policy hashes. The test runner refuses changed sources or policy weights and existing output directories. No gate changes follow inspection of reserved results.

The new plant extends only the isolated surrogate to allow hidden tire-stiffness scaling. Nominal dynamics match the previous RK4 plant to 1e-14 in the contract test. Common actuator limits, sensor estimator, paths, initial state, per-condition noise streams and failure definitions are shared across methods. Friction 0.6, stiffness ×0.65, doubled sensor noise plus 10 ms delay, and service delays 20/100 ms are separate stresses; they are not an exhaustive robustness study. Model computation uses synchronous inference with deterministic simulated availability and one in-flight job, as in the previous surrogate campaign.

## Reproduce

Use the existing installation described in the parent research README. From the checkout root:

```bash
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR="$PWD/integrations/webots/.runtime/numba"
export MPLCONFIGDIR="$PWD/integrations/webots/.runtime/mpl"
"$LANS_PYTHON" integrations/webots/research/revision2/test_gate.py -v

# New output paths are mandatory; committed evidence is never overwritten.
"$LANS_PYTHON" integrations/webots/research/revision2/run.py develop \
  --output "$PWD/integrations/webots/results/revision2-local-development"
"$LANS_PYTHON" integrations/webots/research/revision2/run.py test \
  --freeze "$PWD/integrations/webots/results/revision2-local-development/freeze.json" \
  --output "$PWD/integrations/webots/results/revision2-local-test"

# Verify/report the canonical committed campaign (fixed canonical paths):
"$LANS_PYTHON" integrations/webots/research/revision2/report.py
```

Actual execution used `/workspace/lans-setup/venv/bin/python` with the previously pinned NumPy/SciPy/Torch/SB3 environment and private writable caches. It ran the commands above with canonical output paths `results/revision2-development` and `results/revision2-test`. Full command lines, data, frozen source snapshots and configuration are retained. Six contract tests cover nominal plant parity, immediate invalid/stale/future fallback, sequence regression, no authority for an equal candidate, predicted improvement for the actual command and the state envelope.

`report.py` verifies the complete grid, unique cells, checkpoint/source/freeze hashes, survival sample counts, actuator rate and exact paired LQR equality for all-zero-weight episodes. The CSV retains all cases including failures. Thirty representative compressed traces cover all methods/scenarios at seed 0, 25 m/s, DLC220; missing outputs and unevaluated predictions use explicit NaN fields rather than fabricated zeros. Episode summaries record activation/weights, gate reasons, age, inference and gate wall-time diagnostics. Timing includes cloud scheduling/JIT effects and is not a deadline guarantee.

## Evidence

See [reserved results](../../results/revision2-test/report.md) and [development freeze](../../results/revision2-development/freeze.json). The predeclared primary comparison is gated residual versus LQR in every region. An advantage requires ≥5% mean penalized RMSE reduction, negative paired differences for all five seed means, and no survival decrease. Nominal preservation requires ≤2% increase with no survival loss. Descriptive t intervals across five seed means are reported without a multiplicity-adjusted significance claim. Full-command gating and the old fusion are secondary comparisons, not substitutes chosen after seeing results.

A successful gate test does not prove formal stability or safe fallback outside the validated region. Native Webots transfer of this revision, unseen-path tests, predictor-mismatch calibration, broader independent policy training and publication-level confirmation remain separate work.

Final outcome: all 900 test episodes survived. Gated residual improved mean RMSE by 1.26–2.96% in the first five regions, with all five paired seed means favoring it, and reproduced LQR exactly at 100 ms. Nominal preservation passed, but **no region met the predeclared 5% clear-advantage threshold**. Gated full-command was slightly better in those region means; this study does not establish residual gating superiority. The complete report retains all methods, uncertainty and limitations. No post-test retuning was performed.
