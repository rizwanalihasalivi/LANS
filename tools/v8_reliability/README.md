# V8 analytical reliability experiments

This module preserves the original v8 implementation/evidence and adds audited
analytical supervision, execution and validation experiments. PPO weights,
training, reward and the public17-feature contract remain unchanged. The separate
agent owns PPO incremental-benefit work; integration details are in PPO_HANDOFF.md.

The current experimental controller is traffic_guard.Controller. It includes
original-age source checks, a future-uncertainty/occupancy-tail traffic supervisor,
explicit bounded longitudinal emergency recourse, exact-command cost caching and
nonblocking conic proposals with owner admission. The selected settings remain
R16, horizon2s, quality_factor1.10, secondary_factor1.075 and v8 early identification.
Missing/stale observations retain braking. The emergency mode named
uncertified_emergency_improvement is explicitly an engineering policy without a
safety certificate. Its native traffic transfer has not been established.

Native actuator setpoint slew is0.59rad/s for every matched method, reserving
margin below the0.6rad/s measured center-steering-rate gate. Timing retains the
fixed50ms release origin and every missed tick; complete cycles include inline
trace serialization/write/flush. Response, physics/plant, logging, owner CPU and
context switches are recorded separately. Stable tool-package imports and
separate JIT caches repair the reproduced pytest/campaign cache-name failure.

The prospective V2 Python cohort contains1240 six-second records. Its264 current
hybrid records had zero sampled collisions/corridor failures. All raw dynamics,
initial conditions, traffic transitions, regenerated packet arrivals/freshness,
command FIFO, physical limits and whole-run scores passed independent checks.
The original performance gate failed: final LQR RMSE gain3.8651% (95%cluster CI
2.7978..4.9218%), nominal-optimizer gain1.1644%, and minimum actor progress98.7031%
against the99% requirement. Mean heading/rate RMS are8.2253%/3.5222% above LQR.
The exposed earlier progress fixture was repaired, but that does not establish
the progress condition on all new cases. No production promotion follows.

The28 matched12-second actual-Webots runs completed6720 control ticks with no
corridor failure and measured center-steering rate at most0.594071rad/s. On the
12 matched hybrid runs per method, response misses were119/2880 for original v8
and12/2880 for the current owner; scheduled complete-cycle misses were927 and304.
The strict timing gate failed. These are shared-cloud engineering observations,
including simulator IPC/scheduling delays; they are not WCET or real-world safety
guarantees. This world contains one ideal-sensor car and validates actual1ms
rigid-body/tire/actuator transfer, without native traffic/collision validation.

All26 six-second actual-worker checks completed. The14 current-owner checks,
including stalled/crashed policy/planner processes and stale ego data, passed
their functional gates. The12 matched current cases had3 response misses/1440
ticks against29 for the historical controller; the two extra planner-fault cases
bring the current total to6 misses/1680ticks. Strict timing remains failed.

Verification passed249 core tests and31 historical reviewer tests executed in
isolated processes. Co-collecting the historical tests causes their flat
`environment` imports to collide; original failure logs and isolated results are
retained. A missing optional thread-policy test dependency was installed after
measurements. Additional pinned dependencies are in requirements-reliability.txt.

Evidence retains704 training-only calibration records,192 CBF calibration records,
V1's2309 outcomes,54 exposed V2 development records,1240 prospective V2 records,
two native engineering smokes,28 native records and the actual-worker cohort.
Every failed gate, aborted probe, JIT interruption and startup-harness failure
remains recorded. Completed outcomes were never rerun to obtain a pass. The
original verified v8 development result5.186% remains in its original evidence.
The CBF comparator is a documented LANS-model mechanism adaptation; consult
CBF_PROTOCOL.md and PUBLISHED_REFERENCE_AUDIT.md for its source and proof boundary.

RESULTS.json is the small readable outcome ledger. Complete raw traces,
protocols, frozen sources, unchanged original policies and numerical audits are
stored in bounded ZIPs under evidence/, with SEAL.json and SHA256SUMS. The seal
checks every ZIP member, byte count, CRC, reconstructed source hash and audit
binding. Numerical audit success records data consistency and does not override
failed performance, progress, quality or timing gates.

With the repository Python dependencies installed, verify the sealed bytes:

    python -m tools.v8_reliability.package --verify

Restore into a fresh checkout containing no earlier raw result files; restoration
refuses overwrites and symlinks:

    python -m tools.v8_reliability.package --restore /path/to/fresh/LANS
    python -m tools.v8_reliability.v2_verify
    python -m tools.v8_reliability.verify_runtime native results/lans-reliability-v10/native-validation-v1
    python -m tools.v8_reliability.verify_runtime live results/lans-reliability-v10/live-v1

Actual reruns also require the included original policies at the paths specified
in the frozen protocols and the pinned R2025a simulator installation. Keep new
output directories and new seed namespaces for any later scientific experiment.
No thesis drafts, figures or presentation tables are produced by this module.
