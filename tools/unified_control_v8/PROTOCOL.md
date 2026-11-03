# Corrected conflict timing and causal initial-response study

The user requests further work toward at least 30% whole-run RMSE improvement
against calibrated LQR and strong existing controllers, together with safety,
heading/rate quality, progress and runtime. This is a new finite study; old v6/v7
source, raw outcomes and failures remain unchanged. No reserved cases are opened
by this training-only script. No thesis draft, figure or presentation table.

All candidates share the corrected intersection-occupancy calculation: the first
simultaneous occupancy is the maximum of the interval starts after overlap has
been checked. This fixes false early danger caused by returning the minimum
individual start. Every comparator, including calibrated LQR, receives this fix;
old-baseline/new-controller differences cannot count as comparative improvement.

Freeze exactly four candidates before any new training outcome: legacy v6 with
two-second horizon; original v7 conic with horizon two and predicted quality
factor 1.10; that same conic with causal early-identification readiness; that
same early-identification conic with tracking-SSE ranking and dominance. All use
R=16, identical physical/residual/traffic/ego/proposal constraints and common
nonlinear heading/rate/collision/corridor admission. No additional parameter
search is authorized by this protocol after outcomes.

The early-identification variant uses only sequential received ego observations
and known applied-command history. It replaces the fixed six-informative-sample
wait with evidence readiness: the existing excitation check must succeed, the
current exact RK4 prediction at the causal estimate must agree with measured
lateral velocity/yaw rate within squared error 1e-8, and the compatible empirical
stiffness interval retains the original 0.025 uncertainty floor. A mismatch keeps
the broad 0.3 uncertainty. This is a finite noiseless-sensor simulation model,
not a statistical confidence interval or a real-sensor identification guarantee.
No true plant stiffness enters control; off-grid stiffness, zero excitation and
inconsistent observation tests are required before execution.

The tracking-ranked arm changes the candidate-ranking/dominance objective from
mixed tracking/heading/rate cost to exact predicted lateral-error SSE. It keeps
all original robust per-model heading and steering-rate budgets, actual actuator
mapping, collision and corridor margins. The change is explicit and evaluated
against the same whole-run actual quality gates; it does not redefine RMSE.

Evaluate all four candidates in optimized and adaptive modes on the existing
64 training-only fixtures, plus one matched LQR on those 64 fixtures: exactly
576 six-second episodes. No new PPO learning or seed selection. Select minimum
mean episode RMSE across both modes, with name tie-break, only among candidates
with zero failures, mean heading and rate ratios <=1.10 separately in each mode,
and every episode's progress >=99% of matched LQR. Retain all candidates and
fallbacks. If no candidate qualifies, selection is empty rather than relaxed.

Root campaign preparation must freeze a new prospective namespace and every
actor before outcomes; use all three existing policy endpoints, matched cases
and budgets. Whole six-second mean episode RMSE is primary. Original 5%/1%
promotion gates stay recorded, and the user-requested >=30% gains against each
strong comparison remain separate additional targets. Existing offline 9.34%
quality-admissible and 18.43% quality-failing diagnostics establish neither an
online 30% result nor a certified impossibility bound. A new candidate's success
is not presumed; repeated testing until a favorable cohort appears is not a
valid verification procedure. Final runtime/native transfer remains gated.
