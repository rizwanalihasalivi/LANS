# Publication-validation continuation, declared before outcomes

The user asks to address incremental learning benefit, heading/rate trade-offs,
deadline misses, final untouched evaluation and published-method comparisons.
This new study preserves every prior protocol/outcome, including v8's original
gate pass, unmet 30% request and one deadline miss. No thesis draft, figures or
presentation tables are authorized. All outputs are code, raw data and technical
execution/provenance records.

The expensive conic proposal is moved to a one-request worker. The controller
never waits for it inside a tick. Logical evaluation uses fixed 50 ms proposal
service; actual execution uses process wall time and logical/wall TTL rejection.
Current-state nonlinear robust admission and all physical/freshness bounds stay
in the control owner. Every returned plan is a fallible proposal. Process startup
and warmup are recorded separately. Stale, malformed, crashed and stalled workers
must cause analytical fallback. Finite zero-miss observations are not WCET proofs.

Three fixed asynchronous candidates: original 1.10 predicted-quality factor and
1.10 admission RMS factor; strict 1.00 planner/admission factors; strict 1.00 with
nominal feedback gains but causally adaptive prediction. Compare each in nominal
optimized and adaptive modes on all 64 existing training-only fixtures, plus
matched LQR and the original synchronous v8 nominal/adaptive references: 576
episodes. R=16, two-second horizon, 50 ms sampling and original limits remain.
No true stiffness, future traffic or held-out trajectory enters control.

Select among zero-failure candidates with every case progress >=99% LQR. Prefer
those with mean heading and rate <=100% LQR in each mode, then lowest mean RMSE.
If none meets this stronger quality goal, retain that failure and select the
lowest-RMSE candidate satisfying the old <=110% rule solely for further
diagnostic validation; this does not count as fixing the quality weakness.
If none meets either rule, do not train or promote a replacement controller.

Continue all three original PPO endpoints, seeds 42/43/44, for exactly 16,384
additional steps each (49,152 total). No seed/checkpoint selection or enlarged
budget after outcomes. The matched environment uses the selected deployment
controller, one pending delayed action, the same 17-feature/0.08-radian contract,
actual gated transitions and corridor failure criterion. Shadow LQR is used for
training reward only and receives the same fixture and communication realization.
Reward weights and code must be frozen before learning. Keep all endpoints,
optimizer state, training logs and failures. Delay credit and partial observation
limitations must be stated; no submission is falsely labeled as applied action.

Calibrate two explicitly labeled published geometric-law adaptations on training
fixtures only, with three declared parameter candidates each. Primary-source
verification gaps and departures from published algorithms remain explicit.
These comparisons do not replace closest delay-aware MPC/predictive-filter
benchmarks, establish state-of-the-art performance, or prove novelty.

Freeze all models/source and a new development grid before any outcomes. Evaluate
whole six-second failure-penalized RMSE, headings, steering rate, progress,
clearance/failure and actual timing against matched LQR, nominal/adaptive MPC,
old/fresh PPO hybrids and geometric references. Keep original 5%/1% gate and the
user's separate 30% all-reference target; neither is assumed achieved. Quality
no-regression is a distinct stronger goal, not relabeled by the old 10% allowance.

The user's explicit request now includes untouched final evaluation. A separately
declared final cohort is evaluated once after the controller and all policies
are fixed, regardless of whether the desired gain appears; failures are retained
and cannot trigger tuning or cohort replacement. This is a new validation-only
procedure, not retroactive promotion under v8's original gated protocol. The old
reserved data remain untouched. Native Webots transfer requires the current
Python safety checks to pass and is reported separately from analytical-plant
replay. Never call a simulator containing the same Python plant native validation.
