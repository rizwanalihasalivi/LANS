# Causal initial-response and runtime repair experiment

The user explicitly requests further attempts toward 30% RMSE gain and fixes of
remaining issues. Previous offline diagnostics found 9.343% admissible and 18.429%
quality-failing gains; neither is a deployable policy or a global performance
bound. All old outcomes remain immutable. No draft, figure or presentation table.

## New causal controller

Optimize a local nonlinear prediction through a single convex conic subproblem
per control tick. Use current reconstructed/application-time state, known path,
causally identified stiffness and CV-predicted received traffic only. Hidden
plant stiffness, future traffic truth and stored benchmark trajectories cannot
enter control. Keep R=16, residual/angle/slew/acceleration/freshness limits and the
existing robust nonlinear admission/supervisor. The objective is tracking-first
with explicit predicted heading/rate norm constraints. Project its result through
the original nonlinear actuator/residual mapping before candidate admission.

This is a distinct implementation and must pass its own physical/metric/runtime
validation. It does not retroactively pass v6's failed 1e-12 backend-equivalence
experiment. No numerical equivalence claim substitutes for actual trajectory
audits. Old deadline misses and old 5%/1% gate failures remain in their records.

## Finite training-only selection

Evaluate exactly four shared planner candidates on the existing 64 training-only
cases, nominal optimized and adaptive-only modes: original v6 h=2; conic h=1 with
predicted RMS factor 1.04; conic h=1 with factor 1.10; conic h=2 with factor 1.10.
Use the same conic factor/method in all matched optimized/adaptive/hybrid modes.
Measure separate matched LQR references for each of the two horizons.

Require zero failures, original actual mean heading/rate ratios <=1.10 in each
of the nominal/adaptive modes separately, and every
case's progress >=99% of the matched LQR. Select minimum mean tracking RMSE over
both modes, with a fixed name tie-breaker. No actor/seed selection, no enlarged
search or new learning budget after outcomes. Total calibration: 640 episodes.
The conic solver has at most 60 iterations at 1e-7 tolerances; non-solved/infeasible
proposals return the explicit analytical/grid fallback, never a fake solved plan.

## Prospective evaluation

Freeze the selected source, all three original policy hashes and a new development
cohort before its outcomes: namespace 71413000, route phase 14, amplitude 1.2.
Use all 32 scenario/mirror/speed/stiffness cells, unchanged 24 stress cells with
fresh communication seeds, plus original 19/96 and 14/72 failure regressions.
Keep all LQR/fixed/deterministic/optimized/adaptive/PPO/hybrid modes. Score complete
six-second episodes, failure penalties, original 5%/1% gates and the separately
requested 30% target. Whole-episode RMSE remains primary; 30% is not assumed.

Secondary phase metrics are prespecified: initial 0--1 s and later 1--6 s RMSE,
plus descriptive cutoffs 0.5 and 2 s. Do not choose a favorable cutoff, suppress
whole-episode results or relabel a secondary gain as satisfying the primary 30%
target. These phase analyses investigate initial-transient dominance; they are
not replacements for the original metric. Actor/cell correlations remain.

After logical-time jobs finish, run one fixed nine-check actual-worker functional
cohort (three actors x following nominal/curved ego-blackout/merge crash), six
seconds each, full input-to-issue/cycle timing and 50 ms deadlines. Warm declared
gain/JIT tables separately, record startup, keep every miss and do not retry a
slow case. Final reserved/formal runtime promotion/Webots stay gated; no native
or real-vehicle claim follows from these software studies.
