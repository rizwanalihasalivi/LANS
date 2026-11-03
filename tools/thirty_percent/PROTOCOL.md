# New 30% target: finite offline headroom diagnostic

User instruction: investigate at least 30% improvement. Interpret the requested
metric as mean failure-penalized tracking RMSE reduction against the existing
shared calibrated R=16 LQR. Do not weaken that reference, relabel a crash-driven
ablation gain as controller superiority, change the metric, or delete a weak
case. Old v2--v6 outcomes and 5%/1% decisions remain immutable.

This is a new diagnostic after the user explicitly raised the target. It does
not enlarge the earlier v6 tuning search or open any reserved/final cases.

Use all 32 already observed v6 development LQR episodes, with exactly their
initial conditions, route, six-second duration, actual acceleration sequence and
scripted NPC truth. Freeze input/source hashes before evaluating any new plan.
Reference mean RMSE is about 0.080407756 m; the requested 30% target is about
0.056285430 m. Average episode RMSE, not root of pooled squared error, as before.

## Privileged diagnostic, not a deployable controller

An offline nonlinear shooting optimizer knows true stiffness and the full future
acceleration/NPC trajectories. It chooses 120 steering residuals with the same
0.08 rad requested authority, 0.5 rad angle limit and 0.6 rad/s slew. The nominal
R=16 feedback supplies the shared residual reference. Acceleration is held at the
matched LQR sequence; progress and collision/corridor checks remain explicit.
Because it sees privileged future information and has an offline compute budget,
it cannot be called PPO/hybrid validation, compared as equal online compute, or
used to open Webots. It also is not a certified globally optimal performance bound.

Two fixed solves per case, one zero-residual start each, SLSQP maximum 120
iterations and ftol=1e-10; no restart/search enlargement after outcomes:

- Quality-constrained: minimize tracking SSE with heading and steering-rate RMS
  each <=110% of matched LQR **per episode**, progress >=99%, corridor <=1.75 m,
  and nonnegative realized geometric clearance. Per-episode quality is stricter
  than the original across-cell mean requirement; report both, never infer
  impossibility from a local solver or these stricter constraints.
- Tracking-focused: retain identical actuator, progress, corridor and clearance
  constraints, but omit heading/rate quality constraints to expose trade-offs.
  This is not an admissible improved controller if original quality rules fail.

Normalize the objective by the matched baseline SSE and the constraints by their
reference scales for numerical conditioning. Keep tiny strict-inside margins
(quality energy budget 1.21*(1-1e-6), progress fraction .99000001, corridor margin
1e-8 m, clearance 1e-6 m) so roundoff does not manufacture a boundary pass.
Accept only the original actual quality/progress/corridor/collision limits.

Use forward finite differences with normalized residual step 1e-5 and exactly
the same projected nonlinear bicycle physics as application. Log solver status,
iterations, all proposed final plans and actual violation metrics. If a solve
is unsuccessful/infeasible, retain it and use the matched zero residual as the
explicit feasible diagnostic fallback; do not turn solver failure into success.
Do not choose individually favorable cases between the two diagnostic modes.

Validate zero-residual reproduction to 1e-8 before solves, permitting only
roundoff between Python/compiled controller arithmetic. Independently replay
saved applied commands with Python RK4 to 1e-10. These declared numerical
tolerances do not alter any older verifier or the failed v6 fast-backend test.
All physical/metric acceptance limits are unchanged.

Report every case and balanced eight-scenario/speed-cluster 5,000-draw bootstrap
gain intervals (seed 30413001), including heading/rate/progress/safety outcomes.
Cluster repetition is not independent traffic replication. A successful
privileged plan only establishes finite-case feasibility under its assumptions;
a failed local search does not prove 30% unattainable by every controller.
Any subsequent trainable/online method requires separate training-only design,
three policy seeds, untouched development evaluation and existing final gates.

No thesis draft, figure, presentation table or native Webots run is authorized
by this diagnostic. Output only code, raw trajectories, machine-readable metrics
and execution/verification records. No paid API or external compute is used.
