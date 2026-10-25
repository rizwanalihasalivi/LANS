# Simulation/gate/diagnostic audit

Reviewed core physical plant/sensor/LQR and revision2 gate, revision5 execution/training-distribution evaluator, revision7 compiled execution, revision10/11 diagnostics and reporters. Findings distinguish reproducible interface bugs from intentional research assumptions. No historical source snapshots/results/models changed; no training or threshold tuning.

## Confirmed high-priority bug: held proposals re-timestamped as fresh

Original revision10 and revision11 behavior drivers queried student/teacher only every5ticks (50ms), but called execution_step every10ms with the previous proposal. execution_step automatically submitted whenever the worker was free and stamped the packet with current tick time. Thus observation age was wrong: a proposal actually computed at0ms was recorded as observed40ms at t40ms under zero service delay (reported age0, true age40ms). At20ms service it was recorded as observed20ms (reported age20, true age40). This can artificially restore the frozen gate's freshness authority. Both open-loop rollouts and behavior trajectories therefore needed a corrected replay, not reinterpretation of prior scores.

Focused evidence: `/tmp/simulation-timestamp-probe.json`, using unchanged default behavior to reproduce the old path and the new explicit submission switch to demonstrate the correction. At0ms service the firstfive ticks create5 historical requests versus1 actual policy query/corrected request. At20ms service,3 historical requests versus1 corrected query/request.

Fixes:
- `revision7/kernels.py:93`: optional `submit_request=True` argument; pending delivery and gating continue everytick, but new timestamps/sequences are allocated only for an actual submission request. Default preserves revisions7–9 behavior.
- `revision5/execution.py:40`: matching optional argument in original object interface, used as independent contract reference.
- `revision10/run.py:24`: predictive branches use the same global5-tick submission cadence as actual behavior. `run.py:66` only requests submission on actual query ticks. Submission count/max packet-age telemetry is now recorded and tested.
- `revision11/run.py:65`: actual behavior only submits on policy query ticks. Its hypothetical per-candidate shadow gates still receive fresh constants eachtick by explicitly declared design, distinct from the student stream.
- Both corrected protocols identify `fresh-query-only-v1`; completion captures actual executable `git HEAD`. Both reporters refuse old-schema directories, name the recorded freeze dynamically, and thereby avoid overwriting archived reports with corrected-source provenance.
- Active revision10/11 READMEs qualify archived results until corrected replay. Revision11 malformed Markdown heading spacing also fixed.

Scope of impact: this newly found defect affects revision10/11 diagnostic behavior (and revision10 cost prediction cadence). It does NOT explain the pre-existing revision8 student≈2.16% or revision9 retained-student≈2.07% result: those evaluate the model at each actual available-worker submission, and the kernel default is unchanged. The corrected diagnostics must be used before drawing new headroom/attribution conclusions.

## Verification

19 passing tests captured in `/tmp/simulation-audit-tests.json`:
- new revision7/test_submission.py3: optional default parity,0/20/100ms original-object parity, actual packet age40ms on held output, between-query pending delivery;
- corrected revision10/test_diagnostic.py3: selection agrees with fresh-only rollout cost, branch nonmutation/second-action horizon, severe-delay equality;
- revision11/test_attribution.py2;
- revision5/test_execution.py3;
- revision5/test_evaluation.py2;
- revision2/test_gate.py6.

A later rerun of revision10 tests additionally checks nonzero actual telemetry: exact severe-delay request countceil(steps/10), max packet age≥100ms; all3 passed (23.98s). Compile caches are task-specific `/tmp/lans-audit-sim-numba`. Parent is running frozen corrected72+8 campaigns in separate directories; no result claim is made here before those complete.

## Research limitations observed, not silently changed

- Gate intentionally restricts±0.08rad proposals and≤0.5 blend (≤0.04rad fresh correction), ramps0.05/tick, requires three favorable re-evaluations, and rejects age≥50ms. These constraints make PPO dominance impossible by construction but are not arithmetic bugs. Raising them is not a valid repair of weak-policy performance.
- Gate predicts nominal linear dynamics, fixed local curvature,50ms candidate hold and200ms horizon. Nonlinear tire/geometry/observer mismatch and gate-compatible-vs-lateral objective differences are documented approximations. A new predictor/objective is a controlled research ablation, not a confirmed code fix.
- Sensor delay is delayed measurement assimilation with a nominal estimator, not a validated delay-compensated observer. This is an information/model limitation under the declared stress cases, not proof of a causal2% ceiling.
- Finite5-action teachers/short branches do not prove a maximum achievable gain. No guaranteed5%/10% outcome follows from fixing execution timestamps. Historical training under different semantics cannot be upgraded by labeling old checkpoints as corrected policies.
