# Observation-driven following: development protocol

This is new development, not final thesis benchmarking or a matched superiority
study. Do not open prior confirmation data or tune against it. The v1/v2/v3
controllers, campaigns and evidence stay unchanged.

The selector sees local ego state, accepted raw V2V bytes and unlabeled radar
range/bearing/range-rate scans. Scenario vehicle names, maneuver schedules,
Supervisor poses and scoring truth cannot enter its target-selection interface.
The known route is a map, not a traffic oracle. Every switch logs its evidence.

Freshness: ego/radar 0.2 s, V2V 0.4 s, original source stamps preserved.
Closer obstacles take effect immediately. A farther target/clear road needs
positive departure evidence on three distinct healthy sensor frames. Packet
silence cannot prove departure. Association is one-to-one and geometry-gated;
ambiguous association, capacity exhaustion, stale ego or blind knowledge brakes.
Non-connected vehicles receive local radar-track identities, not invented V2V IDs.
Replay watermarks survive switches. Bounded capacity is fail-closed at 32 tracks.

Development correction after the first 40-run grid: non-connected cut-ins exposed
catch-up consuming the available stopping distance before lateral intent became
observable (six failed episodes retained in `autonomy-dev-v1`). The selector now
caps acceleration with maximum braking when ANY fresh forward observation within
4.5 m of the route violates `2 + 0.4*v_ego + max(0,v_ego²-v_other²)/(2*6)` metres
of bumper clearance. This includes adjacent-lane traffic. It assumes the measured
forward speed and braking model; it is a conservative development guard, not a
proof for arbitrary last-moment incursions. No gains, seeds or scenarios changed.

Python development cases: connected and non-connected cut-in/out, curved route
(radius 500 m), dense two-lane traffic, V2V blackout, dual blackout, packet
loss/jitter/duplicates, and delayed radar. Five seeds: 101, 203, 307, 409, 503.
Each episode is 20 s, 20 Hz control and 10 Hz radar/radio. Ego uses the shared
bicycle plant; other traffic follows declared kinematic paths. All are retained,
including failures. Requirements are no oriented-box overlap, command bounds,
no stale-source use, max braking while selection is uncertain, positive progress,
and autonomous acquisition and return after the maneuver. Replay must reconstruct
decisions and physics from recorded inputs; negative tests must reject tampering.

Native development is conditional on Python checks. Use checksum-verified
Webots R2025a, the long-road fixture and real GPS/IMU/Gyro/Radar/Emitter/Receiver.
Create a separate controller/world; never edit frozen templates. The ego must
discover the intervening vehicle and later return without `retarget` calls from
the scenario. NPC maneuvers may be scripted; ego target selection may not.
Audit all inputs/commands, pose envelopes, native movement and pairwise gaps.
This is simulation development evidence, not collision-free real-world assurance,
string stability, hard real-time validation or perception-stack validation.
