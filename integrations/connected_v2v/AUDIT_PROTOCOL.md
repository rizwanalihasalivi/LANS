# Post-release V2V audit and regression protocol

Parent: `4843c4f1842d042928a953b3394660fa74690de9`. Date: 2026-11-04 UTC.
This audit changes current source. Published source snapshots, failures, thesis
figures and original validation cohorts remain historical evidence for their own
hashes. Final comparative benchmarking remains on hold.

Review covers wire validation and endpoint replay/age state, channel/relay timing,
following/fusion, autonomous and robust association, formation settling, native
adapters, replay/scoring, and conditional-proof/certificate boundaries.

Reproduced faults are recorded in `tests/test_audit_regressions.py`. The original
187 tests passed before edits. The initial adversarial tests produced 21 failures
and four passes; three additional native receiver tests then reproduced crashes
on non-UTF-8 packets. New tests verify fail-safe behavior as well as recovery.

Anonymous unselected tracks may retire only beyond their association horizon
(0.5 s in the initial selector, 2 s in robustness/settling). Missing selected
targets remain pinned; radio peer membership and replay counters persist. Local
scan sequence/timestamp rejection remains global. Anonymous aliases are never
reused. This does not implement radio peer departure or sender-session resets.

Peer scans must also agree with their sender's independently received heading:
wrapped error at the scan timestamp <=0.2 rad, with constant-yaw extrapolation.
This is a consistency rejection gate, not a deterministic sensor-error theorem.
Source confirmation stamps must increase; older fallback measurements remain
usable inside their original TTL but cannot supply new confirmation. Settling
requires two elapsed seconds without a control-observation gap greater than the
declared 50 ms tick; repeated calls cannot manufacture duration.

Run `python -m integrations.connected_v2v.audit_campaign --output NEW_ROOT
--phase PHASE` in the prepared Python environment. No root is overwritten.
The first phase freezes the execution and verification source files and this plan.

| Phase | Cases | Speeds m/s | Seeds | Runs |
|---|---|---|---|---:|
| python-development | all eight settling profiles | 8,12,16 | 6121 | 24 |
| python-development | combined | 16 | 7069 | 1 |
| native-development | all eight profiles | 8,12 | 12037 | 16 |
| python-validation | all eight profiles | 8,12,16 | 21001 | 24 |
| native-validation | all eight profiles | 8,12 | 22003 | 16 |

Every episode is 70 s. Development seeds are exposed regression inputs, including
earlier failures. Validation seeds are new to these profile/stream combinations;
one seed per configuration is a regression cohort, not a broad statistical safety
claim. Python development precedes native development; both must pass before
fresh Python validation, which precedes fresh native validation. Any behavioral
revision after opening fresh validation requires a new root/plan/seeds. Failures
are retained and reported, never removed from a denominator.

Keep existing safety, bounds, source-age, target-return, progress and final-spacing
gates. Replay every run, independently reconstruct every Python input stream, and
independently score every Python/native run. Recheck all 128 previous final native
traces with corrected first/last-sample refinement checks in a separate report.
Run the 1-D and 2-D SMT obligations and negative controls. New 2-D certificates
are generated for the validation `curved` and `combined` episodes at each family's
highest speed, plus `noisy_nonconnected` at 12 m/s. Certificate checks qualify the
finite trajectories under the stated continuous bounds; they do not prove every
future controller execution. Also rerun the deliberately unreachable 150 m
diagnostics: ordinary recovery must fail while expected braking checks pass.

Native receiver fault-injection tests execute the real adapter loops with mocked
device I/O. Actual Webots scenarios are a separate validation step; the mocks
are not Webots dynamics evidence. Invalid bytes are preserved losslessly through
JSON surrogate escaping. Archived experiment replayers continue to require their
declared, source-matched fixture input streams.
