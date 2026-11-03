# Causal initial-response and runtime experiments

This package preserves controller experiments, raw traces and executable audits.
No thesis draft, figure or presentation table was generated. The requested 30%
whole-episode tracking improvement was **not achieved**.

The fixed four-candidate, 640-episode training comparison selected the existing
v6 controller with a 2 s planning horizon. The conic alternative at the same
horizon was 0.042% worse in training RMSE and was separately frozen for an
engineering comparison before any new prospective outcomes. The original
tracking selection was retained. All three original PPO endpoints are reused;
this experiment adds zero learning steps and makes no new PPO-training claim.

The prospective primary cohort gives mean hybrid RMSE **0.073088728 m**, against
**0.076582340 m** for calibrated LQR and **0.073839884 m** for shared nominal
optimized control. Whole-run gains are **4.561903%** over LQR, with clustered 95%
interval [2.709970%, 6.662895%], and **1.017277%** over optimized control, with
interval [0.089926%, 2.458384%]. These fresh cases differ from the v6 cohort;
different cohort means are not a controlled before/after algorithm comparison.

The original overall gate fails because LQR-relative mean improvement is below
5%. The adaptive-only controller has mean RMSE 0.073112941 m, so the hybrid adds
only **0.033118%** over that matched reference. Gains over deterministic and
PPO-only references are 3.877540% and 4.263938%, respectively. The fixed-correction
reference matches LQR on this cohort. No broad controller-dominance claim follows.

Each implementation has 336 hybrid regression/development/stress episodes with
zero observed corridor/collision failures. These finite observations are not a
safety guarantee. The conic alternative's whole-run gains are 4.558868% over LQR
and 1.013197% over its nominal optimized reference. It also fails progress in
development case 4 for all three actors: ratios are 0.988075, 0.989171 and
0.989171, below the unchanged 0.99 requirement. It is not adopted or promoted.

All prespecified phase windows (0.5, 1 and 2 s cutoffs) remain in
`phase_metrics.json` for both implementations. In the primary cohort, 96.7495%
of LQR squared tracking error lies in the first second on average per case.
The later 1--6 s gain is 43.4982% over LQR and 24.8403% over optimized control;
the later 2--6 s gains are 42.0084% and 42.1546%. These are secondary window
results. **They do not satisfy the 30% whole-six-second target.**

The 64-case matched-LQR follow-up explains a prediction-ablation trade-off.
Across that supplementary cohort the full controller's mean heading/rate ratios
to LQR are 1.0890/1.0325, while removing application-time prediction gives
1.1751/1.2188 and fails both 1.10 mean quality limits. Individual profiles remain
available, including failures; this is not an assertion that every profile
passes. Lower RMSE after removing prediction does not establish an overall fix.

The fixed 18 actual-worker functional checks contain 2,160 ticks. The tracking
winner has three response/cycle deadline misses out of 1,080 ticks, with mean
response 16.5237 ms, p95 37.5267 ms and maximum 128.8516 ms. The conic alternative
has zero misses out of 1,080 ticks, mean 9.7095 ms, p95 22.6151 ms and maximum
33.8978 ms. All observed collisions/corridor exceedances are zero. These are
finite shared-cloud measurements with fixed role order, not WCET, target-hardware
or formal real-time validation. Earlier v6 deadline misses remain in their
original evidence. A compute-time gain cannot replace a tracking-RMSE gain.

## Reproduction and verification

Use Python 3.10, the pins in `../unified_control_v5/requirements.txt`, and
`clarabel==0.9.0`. Set single-thread BLAS/OpenMP and a dedicated CLI Numba cache.
Restore the four archives under `evidence/` from the repository root. Original
policies and regression fixtures are in the earlier
`../unified_improvement/evidence/python-results-v2-v3.zip` bundle. Original v6
ablation summary/protocol context is included at its canonical path; these
earlier records are not counted as new trials.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba7-cli
python -m tools.unified_control_v7.package --verify
python -m tools.unified_control_v7.verify
```

The independent verifier checks source/model hashes, all physical traces,
collision/corridor geometry, complete coverage, the fixed calibration selector,
the original bootstrap gates, shared-record identity and actual-worker timing
counts. It verified **1,936 unique new simulation episodes**, comprising 640
calibration, 1,232 prospective and 64 matched diagnostic episodes. The 272 shared
comparator copies are additional records, not extra trials. All 18 functional
traces replay. The focused suite passed **93 tests**. The initially interrupted
empty verification log and the resumed complete log are both retained.

For fresh reproduction use an isolated checkout and preserve the original
source snapshots for historical stages. Calibration/campaign code validates
cached source digests and keeps interrupted evidence. New-only diagnostic and
timing directories must not be reused to seek a more favorable result.

```bash
python -m tools.unified_control_v7.calibrate
python -m tools.unified_control_v7.campaign
python -m tools.unified_control_v7.prediction_tradeoff
# Timing follows completion of competing simulation jobs:
python -m tools.unified_control_v7.live
python -m tools.unified_control_v7.diagnostics
python -m tools.unified_control_v7.verify
```

Source snapshots and protocols precede the relevant outcomes. The conic study is
a distinct causal algorithm; it does not repair the rejected v6 fused backend's
failed strict-equivalence checks. Reserved tests, formal runtime promotion and
final Webots remain **NOT_RUN** under the unchanged gates. Physical, statistical
or hardware claims beyond the observed software experiments are not established.
