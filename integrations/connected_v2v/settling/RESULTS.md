# Final formation recovery and conditional 2-D trace evidence

Python: **240/240 fresh runs pass**, with zero sampled collisions, zero freshness/requested-bound/lane violations and 0 censored stable returns. Worst tail spacing RMS is **0.035396 m**, maximum absolute tail error 0.083661 m, and maximum confirmed-settling onset delay after cut-out 18.70 s. Whole-window correct-target spacing RMS can reach 41.458 m and stopped duration 1.70 s; these transient measures are retained. The worst whole-run unconditional headway RMS is 51.827 m, and the worst post-cut-out unconditional headway RMS is 41.174 m. Maximum post-cut-out nominal head gap is 128.020 m. Across development and validation, all 336 traces and 5,821,200 actor-pair intervals have a continuous conditional certificate. The minimum conservative Euclidean clearance lower bound is 0.000306 m.

Webots: **80/80 fresh runs pass**, with zero sampled collisions, zero freshness/requested-bound/lane violations and 0 censored stable returns. Worst tail spacing RMS is **0.097552 m**, maximum absolute tail error 0.207090 m, and maximum confirmed-settling onset delay after cut-out 28.15 s. Whole-window correct-target spacing RMS can reach 48.219 m and stopped duration 3.65 s; these transient measures are retained. The worst whole-run unconditional headway RMS is 55.452 m, and the worst post-cut-out unconditional headway RMS is 49.599 m. Maximum post-cut-out nominal head gap is 133.594 m. Across development and validation, all 128 traces and 2,217,600 actor-pair intervals have a continuous conditional certificate. The minimum conservative Euclidean clearance lower bound is 0.000190 m.

The verifier retains the first valid separating axis. Its minimum clearance lower bound is not an actual nearest-body distance estimate or the strongest bound over all axes.

Native qualification includes 4,368,000 motion samples. Maximum sampled coordinate acceleration is 11.520182 m/s², yaw rate 0.250072 rad/s, planar speed 16.037619 m/s and recorded bridge deviation 0.001435 m. Requested-versus-measured acceleration discrepancy reaches 6.579729 m/s². Thus a requested braking bound is not substituted for actual native response. Finite motion checks support, but do not prove, the continuous derivative premises.

All independent aggregate/source/wire/pacing/guard-phase audits and regenerated Python inputs pass. Six exported 2-D SMT obligations replay as UNSAT; the omitted-bridge control is SAT. All five semantic corruption controls are rejected after rehashing. Both final unreachable diagnostics pass their expected fail-safe checks and retain ordinary recovery FALSE.

The unreachable Python diagnostic brakes from 12 m/s. The native unreachable fixture starts at rest and inhibits launch; it is a cold-start fail-safe check, not a moving stopping experiment. Moving native information loss is exercised separately by the ordinary blackout profiles.

The specifically exposed original 150 m failure, noisy/non-connected traffic at 12 m/s and seed 2003, also passes a separate known-failure regression. Its new 70 s tail RMS is 0.045684 m and stable-return onset delay is 0.00 s. Within the original first 35 s it has 241 consecutive correct fresh head samples (12.05 s by the declared 20 Hz count). Its independent audit and continuous all-actor certificate (4,200 pair intervals) pass. This exposed seed is regression evidence, excluded from fresh denominators. The older 35 s failure remains unchanged; the architecture and horizon differ, so no matched causal percentage is claimed.

## Python fresh profile coverage

| Profile | Runs | Worst tail RMS (m) | Tail max error (m) | Max onset delay (s) |
| --- | ---: | ---: | ---: | ---: |
| curved | 30 | 0.023804 | 0.046417 | 11.10 |
| dense curved | 30 | 0.028753 | 0.048978 | 11.40 |
| noisy nonconnected | 30 | 0.030126 | 0.083661 | 16.25 |
| burst misses | 30 | 0.035396 | 0.070885 | 12.20 |
| occlusion brake | 30 | 0.019873 | 0.047382 | 12.10 |
| dual blackout | 30 | 0.023716 | 0.058424 | 11.10 |
| v2v blackout | 30 | 0.027674 | 0.050512 | 11.10 |
| combined | 30 | 0.018942 | 0.050344 | 18.70 |

## Webots fresh profile coverage

| Profile | Runs | Worst tail RMS (m) | Tail max error (m) | Max onset delay (s) |
| --- | ---: | ---: | ---: | ---: |
| curved | 10 | 0.097552 | 0.160940 | 14.20 |
| dense curved | 10 | 0.091651 | 0.183719 | 15.25 |
| noisy nonconnected | 10 | 0.095631 | 0.165475 | 25.70 |
| burst misses | 10 | 0.084935 | 0.144833 | 14.70 |
| occlusion brake | 10 | 0.087548 | 0.156603 | 19.15 |
| dual blackout | 10 | 0.085752 | 0.157663 | 13.90 |
| v2v blackout | 10 | 0.090490 | 0.207090 | 14.00 |
| combined | 10 | 0.095243 | 0.166179 | 28.15 |

## Failed history retained

An always-narrow exploratory guard collided during unobserved cut-in; all eight early Python probes failed. The first complete frozen development grid passed 71/72, exposing lost relay/exit association. Priority original-byte forwarding, fresh cooperative anchors and measured membership addressed those failures. The next frozen candidate passed 72/72 Python development and 16/16 native development but only 239/240 fresh Python runs: combined/16/7069 lost all useful head paths after a brief return. It had no collision but failed recovery/progress; native validation stayed closed.

A 4 m/s-only pacing probe then reproduced combined/16/6121 path loss. The corresponding development campaign was aborted with 21 completed cases and an explicit ABORTED marker; it is not a complete passing cohort. Analysis found unnecessary adjacent-traffic stops after the in-lane predecessor was already admitted. Three distinct fresh unblocked observations after an observed cut-in now establish lane-aware following while initial approach remains conservative. Six source-frozen probes, including both exposed combined failures, passed before the replacement full grid. No 9001-series final validation seed was opened during these common-controller amendments.

The next native campaign passed 16 development runs, then was aborted after 42 fresh records: 41 passes and one conservative vehicle-envelope overlap in noisy/non-connected/8/8011. Requested -6 m/s² was physically realized at about 2.8 m/s² because the unchanged Car velocity motor ramp uses time0To100=10 s. Applying friction braking in SPEED mode alone failed that case; a TORQUE-mode probe resolved it but failed three other recovery/pose cases. All probes and the partial native source/data are preserved.

The accepted native-only refinement plans earlier braking with a 2.5 m/s² allowance and 0.8 s reserve from fresh observed guard objects. It preserves the stable SPEED-mode plant, adds a 0.3 s brake-release hold and logs/replays nominal commands, native overrides and API readback separately. The accepted adapter uses stable SPEED-mode motor stopping with friction intensity zero; mixing locked friction brakes with the velocity servo failed a curved combined probe. Pinned R2025a Radar source also confirmed that partially visible targets have azimuth clipped to the physical aperture edge. The adapter rejects the ambiguous 0.33–0.35 rad fringe, preserving unknown/never-clear semantics and matching the Python central aperture. Friction, mass, geometry and the original vehicle ramp are unchanged. The common Python source and its 240 fresh results remain unchanged. Native development now covers both 8/12 m/s at seeds 6203, exposed 8011 and exposed 12037 (48 runs), followed by entirely new 16001-series seeds.

The resulting native-v3 campaign passed 32 development and 79/80 fresh trials. Combined/12/12037 develops steering divergence near 18.5–18.75 m/s, then leaves the lane; it is retained as an actual failed confirmation. The replacement caps native recovery setpoints at 16 m/s and qualifies observed planar speed at most 16.5 m/s, preserving a catch-up margin over the 8/12 m/s head cruise. Heading/lane and all other gates remain unchanged. This declares a native steering operating envelope, not a stability theorem at arbitrary speed. The new fresh seeds are unopened 16001-series inputs.

All complete failed grids, partial development, raw probes and exact frozen sources where available remain archived. Exploratory probes without a contemporaneous source freeze are labelled with that provenance limitation. Earlier 150 m 35/36 evidence remains unchanged and is not relabelled.

## Exact scope

The head uses only its own state and actually received member beacons. Beyond a 60 m reserve gap it lowers its goal by at most 4 m/s; unavailable member beacons use the same bounded reduction. The head must return to cruise in the final-window gate. This is finite-scenario connectivity support, not a universal link-retention invariant. The direct range remains 150 m in Python links, native Emitter fields and runtime configuration.

The 2-D result is a posteriori finite continuous trajectory certification under the stated contract; it is not prospective full-controller invariance or real-world safety certification. Final comparative benchmarking remains on hold.
