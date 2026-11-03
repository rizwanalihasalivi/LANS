# Raw investigation of the requested 30% tracking gain

The user raised the desired mean RMSE improvement to at least 30%. This new
study keeps the existing calibrated R=16 LQR reference, physical limits,
acceleration sequences, initial conditions and all 32 observed v6 development
cases. Original v6 source/results and 5%/1% decisions are unchanged. No reserved
or Webots cases were opened. No thesis draft, figure or presentation table is
generated.

The existing reference mean is 0.080407756 m; a 30% reduction requires at most
0.056285430 m. The actual frozen online hybrid remains at 0.076526297 m,
4.827% better than LQR and 1.131% better than optimized nominal control on that
cohort. Results below are **privileged offline diagnostics**, not that controller.

The first fixed local-SLSQP diagnostic retained all 64 solves and every fallback.
23/32 quality-mode and 28/32 tracking-mode candidates hit their iteration cap.
It is not a performance ceiling. The subsequent joint conic diagnostic addresses
projected-gradient flatness, optimizes the original mean-of-episode-RMSE objective,
and uses the original across-case mean heading/rate budgets rather than stricter
per-episode budgets. Both modes have exactly six convex subproblems with fixed
line-search fractions; no favorable case mixing or post-result budget extension.

The joint quality-constrained diagnostic finds 0.072895168 m mean RMSE, a
**9.343% gain**, with original physical/progress/mean-quality checks passing.
The tracking-focused diagnostic finds 0.065589527 m, an **18.429% gain**, but
heading RMS rises about 48.94% and steering-rate RMS about 159.80%. It fails the
existing quality requirements. Neither finds 30%.

Neither number is a deployed PPO/hybrid gain: the optimizer knows true stiffness
and complete future traffic/acceleration and solves all 32 cases jointly. The
convex subproblem has local linearizations and nonlinear projection; it is not a
certified global nonlinear optimum. Failure to reach 30% does not prove every
possible controller is incapable of doing so. Bootstrap intervals describe this
fixed optimized cohort; they are not independent out-of-sample policy validation.

An additional exact conditional calculation shows that keeping the baseline's
first 250 ms error prefix unchanged leaves at most 28.978% RMSE gain even if all
later error is zero. The average per-case first-second squared-error fraction
is 96.449%. This identifies the initial transient as essential; it is not an
unconditional actuator reachability bound or a general impossibility proof.

## Reproduce and verify

Use Python 3.10 and the existing pins in `../unified_control_v5/requirements.txt`,
plus Clarabel 0.9.0 from `requirements.txt`. The recorded environment installed
only that solver; NumPy/SciPy/OSQP pins were unchanged. The interpreter lacks pip,
so the existing uv installer was used with `--no-deps` and trusted TLS.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba30-cli
python -m tools.thirty_percent.run
python -m tools.thirty_percent.prefix
python -m tools.thirty_percent.run_conic
python -m tools.thirty_percent.verify
```

Original directories are never overwritten. Restore the raw evidence for
read-only checks. Fresh execution requires new output locations or an isolated
checkout; frozen snapshots preserve the original source for cached reproduction.
Keep the production CLI and pytest JIT caches separate:

```bash
NUMBA_CACHE_DIR=/workspace/lans-setup/numba30-tests python -m pytest tools/thirty_percent -q
python -m tools.thirty_percent.package --verify
```

`PROTOCOL.md` and `CONIC_PROTOCOL.md` were recorded before their respective solves.
The evidence archive includes copied baseline input traces, every local candidate
and fallback, every joint solver/line-search outcome, final controls, source hashes,
runtime versions, installation/failure logs and independent verification. There
are 192 candidate/fallback/final diagnostic traces, 23,040 replayed steps, based on
the same 32 observed fixtures; those are not 192 independent traffic trials.

The verifier checks true-model RK4 motion, fixed acceleration/NPC inputs, actuator
limits, requested residual authority against an independently recomputed LQR,
all safety/quality/progress metrics, solver fallback semantics, coverage and the
unchanged bootstrap calculations. Corruption tests reject invented baseline labels.
The joint acceptance test explicitly checks mean episode RMS, not pooled energy
or a different per-case quality rule.

30% remains **NOT ACHIEVED**. Any causal controller designed from these diagnostics
needs separate training-only development and untouched multi-seed evaluation.
