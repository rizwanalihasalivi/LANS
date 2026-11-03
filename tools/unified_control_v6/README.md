# Proposal-completion Python experiments

This package runs experiments and preserves raw evidence. Per the user's latest
instruction, no thesis draft, figure or presentation table is generated.

`PROTOCOL.md`, `ABLATION_PROTOCOL.md` and `FUNCTIONAL_PROTOCOL.md` specify the
finite planning search, component experiments and actual-worker functional
checks. Source/model/protocol snapshots are sealed separately before each study.
Previously failed v2--v5 runs and thresholds remain unchanged.

The training-only selector retained per-knot nonlinear shooting at a 2 s horizon.
The fresh three-seed development gate records 4.827220% gain over calibrated LQR
and 1.130987% over the shared optimized nominal reference. Both lower clustered
95% gain bounds are positive. The original overall promotion gate still fails
because 4.827220% is below 5%. Reserved, full formal runtime promotion and final
Webots must not be relabeled passed. The adaptive-only reference remains essential
for interpreting the contribution of model adaptation versus PPO.

## Execution

Use Python 3.10 with the pins in `../unified_control_v5/requirements.txt`. The
recorded environment is `/workspace/lans-venv`. Run from the repository root:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba-v6-canonical
python -m tools.unified_control_v6.calibrate
python -m tools.unified_control_v6.campaign --stage all
python -m tools.unified_control_v6.ablation
# Run timing only after competing simulation processes finish:
python -m tools.unified_control_v6.live
python -m tools.unified_control_v6.raw_analysis
python -m tools.unified_control_v6.verify
```

Use a separate JIT cache for tests so pytest package aliases cannot contaminate
the production CLI cache:

```bash
NUMBA_CACHE_DIR=/workspace/lans-setup/numba-v6-tests python -m pytest \
  tests integrations/unified_lans/tests tools/unified_campaign/test_campaign.py \
  tools/unified_improvement/test_verify.py tools/unified_control_v4/test_control.py \
  tools/unified_control_v5/test_control.py tools/unified_control_v6 -q
```

Output directories are new-only or hash-validated cached stages. Do not overwrite
original traces. Restoring the evidence is sufficient for read-only verification;
fresh reproduction should use an isolated checkout with original snapshots for
hash-frozen historical stages. The pre-execution source snapshots can include
auxiliary export code written before the user paused artifact generation. That
code was never executed; it is preserved only for original digest integrity and
is not an active export workflow in this handover.

Canonical planned coverage is 448 training-only calibration episodes, 752 formal
development/regression/stress episodes and 384 supplementary component episodes.
They are distinct designs, not one independent sample. Parallel workers execute
the same frozen case IDs. Their intermediates are not extra trials; byte-identical
copies are preserved through content-checked archive aliases, while differing
intermediate files remain in full.

The component study uses a fixed seed-42 policy and 16 scenario/traffic fixtures
with four profiles each. Report clustered comparisons rather than treating
individual ticks or correlated profiles as independent. Warning labels are a
current-truth CV proxy; controlled prediction/ranking scores are model diagnostics,
not actual future collision labels or realized full-plan counterfactual outcomes.

All component contrasts remain in machine-readable analysis, including mixed
findings: full-system RMSE is 2.102% worse than the no-application-prediction
ablation on this supplementary cohort. The additional PPO contribution is only
0.0215% in the single-actor component comparison; it is not a major learned
advantage. These results require further investigation rather than case removal.

Actual-worker checks are limited functional diagnostics with all three fixed
policies, not a bypass of the unopened formal runtime or Webots promotion gates.
The study reuses earlier policy weights; it does not claim new PPO training,
pure-PPO superiority, real-vehicle validation or certified safety.

The original nine functional checks retain four >50 ms misses out of 1,080 ticks.
`FAST_PROTOCOL.md` specifies a separate fused projection/scoring implementation
and a complete nine-check rerun after paired numerical regression. The first
cross-process historical comparison failed its 1e-12 bound at approximately
2.073e-10; that attempt and its diagnosis remain in the evidence. A paired fresh
original/fused comparison isolates the implementation effect without claiming
bitwise historical reproducibility. No failed check is relabeled passed.

The paired regression also failed the unchanged 1e-12 bound (a command difference
of about 8.255e-11). The prototype is rejected and is not the selected production
backend. No fast-backend timing result exists. Its code, strict failures and
diagnosis are retained; the original four timing misses remain unresolved.

## Evidence

The four archives in `evidence/` restore the canonical `results/proposal-completion-v6`
paths, all outcomes, exact source bytes, analysis JSON and execution logs. Original
policies and v3 regression fixtures remain in the earlier
`../unified_improvement/evidence/python-results-v2-v3.zip` bundle.

```bash
python -m tools.unified_control_v6.verify_archives
python -m tools.unified_control_v6.verify
```

The read-only verifier recomputes physical/FIFO transitions, geometric clearance,
failure penalties, complete coverage and the original bootstrap gate. Corruption
tests reject altered RMSE, clearance labels and applied commands even if an edited
trace is given a refreshed raw hash. Numerical integrity is not a formal stability,
safety or statistical-superiority proof.
