# V2V audit — 4–5 November 2026

Audit baseline: `4843c4f1`, branch `experiments/python-validation-v2`.
The baseline suite passed **187 tests**. Nine reproducible defect groups were
fixed, with 34 additional adversarial regression cases. The complete suite now
passes **221 tests**. All 81 new 70-second scenario runs passed their existing
gates, including 40 runs on fresh seeds, with zero sampled collisions.

| Finding | Consequence | Correction and regression coverage |
|---|---|---|
| Wire IDs collided with private `peer-1`/`track-1` aliases | A valid ego identifier caused `cannot follow self` and stopped control. | Separate internal ego namespace; both IDs tested across all three autonomous selectors. |
| Anonymous tracks accumulated for the controller lifetime | Repeated unrelated encounters exhausted capacity and permanently faulted subsequent scans. | Retire only expired, unselected association memory; unique monotonic aliases; preserve selected missing targets and all endpoint replay state. Forty sequential encounters and pinned-target cases exercise bounded storage. |
| Confirmation used unequal rather than increasing source timestamps | Falling back from newer radar to older still-fresh V2V counted the same observation again and enabled the narrower guard early. | Increasing confirmation high-water mark; independent auditor uses the same temporal requirement. |
| Settling counted calls rather than elapsed observation time | Forty calls at one timestamp could report recovery complete; gaps could also count as stability. | Two elapsed seconds of unblocked observations at contiguous control intervals, with explicit duration telemetry. |
| Cooperative scan consistency omitted orientation | A stationary peer could supply a scan rotated 180 degrees while passing position/velocity checks. | Check wrapped heading agreement at the original scan timestamp, including yaw extrapolation. |
| Trace certificate accepted zero/negative duration | A negative rotation allowance could certify already overlapping rectangles. | Require a strictly positive finite interval and pose triples before exact arithmetic. |
| Native refinement skipped boundary samples | Last-frame roll/pitch, first yaw rate and initial acceleration could escape qualification. | Check every control pose and include the rest-to-first-motion interval. NaN and adverse boundary controls are rejected. |
| Native receipt logging decoded malformed bytes strictly | Invalid UTF-8 could crash the running adapter before/after packet rejection. | Lossless JSON surrogate escaping and matching replay decoding; real adapter loops tested with faulty device input. Shared earlier Webots/recovery/formation logging and replayers also corrected. |
| Archive verification allowed vacuous/incomplete success | Empty checksums, omitted declared archives, duplicate ZIP members, empty member inventories or inconsistent inventory sizes could pass. | Require a nonempty inventory, exact checksum/file-list agreement, unique safe member paths and matching archive/member sizes and hashes. Five negative cases now fail and valid extraction preserves exact bytes. |

## Review coverage

| Area | Audit and validation |
|---|---|
| Protocol, endpoint and channel | Reviewed bounded JSON schema, duplicate fields, reserved IDs, original observation age, future/regressing stamps, per-sender replay, capacity, delay/loss/duplicate queues and range-at-transmission semantics; existing regression suite passes. |
| Platoon, radar fusion and formation | Reviewed source TTLs, source disagreement braking, local-state failure, retargeting, gain/speed envelopes and native setpoint behavior; existing tests pass. |
| Autonomous/robust/settling selection | Reviewed association, anonymous identity lifetime, positive departure, cooperative evidence, confirmation, stopping guards and recovery; fixed the issues above. |
| Native adapters | Reviewed GPS/IMU/radar conversion, range/FOV limitations, original-byte forwarding, receiver queues, braking reserve, setpoint/readback and logging. Fault injection is identified separately from actual Webots execution. |
| Evidence and proof | Reviewed replay/input regeneration, independent metrics, archive hashes, the 1-D contract and 2-D interval witnesses; fixed invalid duration and native endpoint qualification. Source-frozen old results stay attached to their original code. |

## Validation record

The exact staged cohort is declared in [AUDIT_PROTOCOL.md](AUDIT_PROTOCOL.md).
Every episode is 70 seconds. Every run has controller replay and independent
scoring; all Python input streams were regenerated independently of the controller.

| Cohort | Passed | Sampled collisions | Worst final-5-s spacing RMS | Maximum settling delay after cut-out |
|---|---:|---:|---:|---:|
| Python development | 25/25 | 0 | 0.029316 m | 14.50 s |
| Webots development | 16/16 | 0 | 0.101511 m | 29.90 s |
| Python fresh validation | 24/24 | 0 | 0.029019 m | 12.80 s |
| Webots fresh validation | 16/16 | 0 | 0.106826 m | 20.85 s |

This is one fresh seed per profile/speed configuration, not a broad statistical
safety claim. The pass gates also require correct target return, progress, leader
cruise recovery, source freshness, actuator bounds and corridor compliance.

- All **221 tests** pass; 5,000 deterministic malformed-byte inputs were rejected
  without parser/endpoint crashes.
- The 1-D reference proof reran **12 UNSAT obligations and five SAT negative
  controls**, followed by independent replay of the exported SMT files. The 2-D
  proof reran **six UNSAT obligations and one SAT negative control**.
- All six predeclared fresh trajectory certificates pass: curved/highest-speed,
  combined/highest-speed and noisy non-connected/12 m/s in each simulator.
  Together they certify **95,200 actor-pair intervals**, under the declared
  continuous body/pose/acceleration/yaw bounds. A separate development smoke
  certificate also passes; no certificate is claimed for every future trajectory.
- Corrected native boundary qualification passes **128/128 historical final
  Webots traces**. This rechecks existing motion records; it is not a new physics
  run and does not change their frozen controller source.
- New Python and actual Webots unreachable-150-m diagnostics pass expected
  braking checks. Their ordinary formation-recovery outcomes remain **failed**
  and are excluded from the successful scenario-cohort totals.

The execution snapshot contains 115 files. The archive-verifier correction was
applied after the cohorts completed and is recorded separately in
`post-campaign-amendment.json` and `post-campaign-verification-source/`; controller,
simulation, scoring, input regeneration and certificate code stayed unchanged.
The original campaign source manifest was not rewritten. Reproduction with the
current tree starts a NEW campaign root, as required by the protocol.

Raw traces, source snapshots, complete test/proof reports and amendments are under
`results/v2v-audit-20261104-v1`. The [audit evidence archive](evidence/audit-20261104/INDEX.md)
preserves them with per-member hashes and an archive inventory. Previously
published thesis results remain evidence for their original revisions.

This is a simulation/controller audit within the documented operating envelope.
Radio identities remain unauthenticated, sender reboot requires an explicit
session design, and a missing selected target still causes braking. Recovery
requires a fresh sensing/communication path; 150 m radio range cannot guarantee
one. The 1-D proof and finite 2-D trajectory certificates retain their stated
assumptions. Final comparative benchmarking remains on hold.
