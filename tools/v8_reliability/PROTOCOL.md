# V10 reliability-first development

Parent: c394184a. User assigns PPO learning benefit to another agent. This work uses the
verified v8 conic/early-identification controller as the fixed base and addresses
other reliability, quality, validation and comparison weaknesses. No PPO
training, reward, feature-contract or policy-weight changes are authorized here. Preserve all earlier source/evidence.
This stage is diagnosis and development; it does not promote a candidate.

Use only archived training diagnostics and exposed native failures for repair.
V9's frozen final evaluation must not be reused to tune or select a controller.
Do not weaken original physical limits, freshness, safety, >=99% progress,
whole-run failure-penalized RMSE, heading/rate or 5%/1% gates. The 30% mean and
lower-confidence targets remain separate outcome flags and are not promised.

First reproduce shared crossing failures, diagnose infeasibility/braking and
recovery from stale proposals. Add meaningful regression controls. Retain every
unsuccessful probe. Proposed architectural changes get explicit versions and
new inputs before confirmation. Any new controller/supervisor must be used by
matched analytical and learned baselines so safety fixes are not attributed to PPO.

Diagnose timing with the full native sensor-to-actuator cycle, output logging
and scheduled completion recorded separately. Cold startup/JIT is recorded;
stale/crashed/stalled workers may not block the control owner. Never shorten a
measured interval, drop a slow run, reset its schedule or hide a deadline miss.

Training/confirmation plans and source freezes will be recorded before their
outcomes. Simulation safety, learned benefit and the requested 30% gain are
independent gates; report any unmet gate directly. No new thesis/figures here.

## Scope clarification before confirmation

Use v8's selected conic-v8-early-id settings: R=16, horizon=2 s,
quality_factor=1.10, early_id=True, tracking_only=False, adaptive feedback.
The v9 RuntimeController is used only as an asynchronous execution wrapper
around that unchanged v8 controller, not the strict nominal-feedback v9 selector.
The other agent owns PPO-specific optimization. Use all three existing frozen
PPO endpoints without seed/checkpoint selection. No drafts, figures or tables.

Initial crossing diagnosis found max-braking failures shared with LQR. A new
analytical emergency fallback searches six bounded accelerations using current
received traffic, original ages, committed command FIFO and three model points.
Angle/rate/acceleration, corridor, source TTLs, buffer and growing uncertainty
are retained. Fresh padded-feasible recourse is preferred. If every padded
rollout fails, a positive physical-envelope rollout that strictly improves
the worst padded margin may replace the already-infeasible brake. This mode
is explicitly recorded as uncertified_emergency_improvement. It is a new
emergency policy, not relaxed steering/PPO admission or a safety theorem.
It can temporarily exceed cruise by at most the declared 4 m/s prediction
reserve; this must be separately qualified before any native traffic transfer.
Historical failure fixtures are development regressions only.

Owner-side cost caching must be numerically equivalent to v8 admission; all
keys include the proposed actual bounded command and model/traffic state.
Asynchronous timing is compared using identical frozen actor weights.

## Fixed training-only calibration before outcomes

Existing v8 calibration's 64 training fixtures are permitted (not its prospective
or reserved data). Run exactly 704 six-second records: one common-recourse LQR
and original v8 synchronous optimized/adaptive, plus four new optimized/adaptive
arms on every fixture. Arms: cached synchronous v8 at original 1.10 limits;
asynchronous v8 with planner/owner factors 1.10/1.075, 1.05/1.075, 1.05/1.05.
All maintain adaptive feedback in adaptive mode, original R=16 and 2 s horizon.
No PPO policies or training are used in calibration. Save every raw record.

Eligible arms require zero failures, >=99% matched LQR progress on every case,
and <=110% mean heading/rate in each mode. The additional quality-repair goal
requires no higher heading/rate than the original v8 in either mode, at least
1% reduction in one of those four quantities, and no more than 1% mean RMSE
loss relative to v8 across the two roles. Prefer arms satisfying that goal,
then lowest mean episode RMSE. If none satisfies it, select the best eligible
arm only for diagnostics and explicitly leave the quality weakness unresolved.
If no arm is eligible, do not open final confirmation. Preserve every failed arm.
Source hashes and exact fixture definitions freeze before these outcomes.
