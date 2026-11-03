# Broader following and perception validation

Prepared before the new outcomes. This is a finite extension of autonomous
following, not final thesis benchmarking or a superiority experiment. Preserve
all prior controllers, archives and held-out data. Do not manufacture outstanding
results by changing thresholds, dropping seeds or hiding failures.

The follower receives only local native/simulated sensing, unlabeled radar
range/bearing/radial-speed and accepted V2V packets. The route is a known map.
NPC maneuvers are scripted; ego target switches are observation-driven. No traffic
truth, missed-target labels or scenario switch times may select the ego's target.

Fallible radar cannot prove departure by absence. The new controller must retain
an unseen predecessor and brake until reacquisition or three distinct positive
exit observations. Track memory may support identity reacquisition for <=2 s;
it must never refresh measurement timestamps or extend the 0.2/0.4 s radar/V2V
control TTL. Ambiguous association and capacity exhaustion brake. Requested
acceleration remains [-6,2.5] m/s²; steering/rate remain 0.5 rad / 0.6 rad/s.

Python uses the shared bicycle ego plant and declared kinematic NPC routes,
20 Hz control / 10 Hz radar/radio, 32 s episodes. Eight profiles: curved,
dense_curved, noisy_nonconnected, burst_misses, occlusion_brake, dual_blackout,
v2v_blackout and combined. Speeds: 8, 12, 16 m/s. Development seeds: 701, 709,
719 (72 trials). Conditional fresh validation seeds: 1009,1013,1019,1021,1031,
1033,1039,1049,1051,1061 (240 trials). Freeze source before validation. Development
seeds may diagnose defects; validation outcomes must not guide tuning on those
same seeds. A required fix invalidates promotion, preserves failures and needs a
new declared validation cohort. These are new trials, not old reserved campaigns.

Perception models include actual line-of-sight occlusion, shuffled anonymous
returns, Gaussian range/bearing/rate noise, independent misses, a 1 s burst,
measurement latency with original source stamps, plus communication loss/jitter/
duplicates and 1.5 s blackouts. Miss decisions are not a health oracle supplied
to the controller. Noise/miss severity is fixed in the profile source before runs.
Unknown coverage is always marked incomplete for departure inference.

Native Webots uses a physically bounded curved/straight two-lane road ribbon,
real Radar/GPS/IMU/Gyro and Emitter/Receiver, measured body lateral velocity and
Webots physics. Six profiles (all except v2v_blackout and combined), 35 s.
Development: speed 8, seeds 811,821 (12 trials). Conditional validation: speeds
8,12, seeds 2003,2011,2017 (36 trials), with frozen sources. Dense profiles use
eight native Cars, including non-connected vehicles; others use three. Native
occlusion is enabled. Misses and latency are applied to actual anonymous returns,
not synthetic observations of another robot. Retain raw and adapted sensor data.

Required checks: complete expected tick/sample counts; replay accepted inputs,
target changes, source ages and commands; source/world/controller hashes; no
sampled oriented-box overlap (ALL vehicle pairs, not just ego), road/pose or
requested-bound violations, no stale-source use, max braking when uncertain.
Also require meaningful progress (>25 m and >=40% of cruise distance), intervening-vehicle
acquisition and return to the front vehicle in fixed stable windows. Report speed,
gap, censoring, progress, fallback and recovery observations per run. A safe stop
without demonstrated recovery is not a complete pass.

Use at most three independent Python worker processes / two Webots processes
on the five-CPU machine. Each has unique outputs, RNGs and Xvfb display. No output
overwrite or interrupted partial reuse. Log and retain failed/invalid trials.
Native evaluation is conditional on all Python development checks passing.
Native validation additionally requires native development and Python validation.
Recompute evidence with an independent stdlib scorer and negative tamper checks.
Archive raw data, source, protocols and checksums before Git commit/push.

This does not validate a learned perception stack, arbitrary geometry or all
possible incursions. Unobservable hidden traffic can require an indefinite safe
stop; no algorithm can infer its departure from silence alone. Publication of the
cloud snapshot remains a product UI action. Final thesis comparison stays on hold.

## Development amendment before fresh validation

The first 72-run development grid had no safety/freshness/bound violations but
11 recovery/progress gate failures. In combined faults, the head vehicle could
leave the stopped follower's direct radio range. Add bounded-rate neighbor
forwarding: one accepted original beacon per node per 100 ms, round-robin by
origin, <=0.25 s old at forwarding. Original bytes/IDs/timestamps stay unchanged;
the endpoint still enforces its original 0.4 s TTL/replay watermark. Non-connected
vehicles do not transmit or relay. This is an application-level simulated relay,
not a standardized radio or network-capacity guarantee. Blackouts also mute relays.

The recovery counter distinguishes target selection from actuator intervention:
a fresh correctly selected head vehicle still counts while the independent
nearby-traffic guard brakes. Progress, collisions, source ages and bounds remain
separate unchanged gates. The report must retain stopping and spacing metrics;
identity reacquisition is not equivalent to formation settling. Rear-lane NPCs
slow after 18 s to preserve their own fixture headways after the scripted merge.
Prior probe/grid data stay preserved; the corrected development grid must pass
before opening the unchanged fresh validation seed list.

Second development diagnosis: the inherited selector incorrectly capped radio
target relevance at the radar's 120 m range; fresh radio knowledge (direct or
relayed) is now usable out to 300 m, without changing any actual 150 m radio link
or source TTL. No state is extrapolated beyond its existing control freshness.
Noisy lateral derivatives from a vehicle still centred in the adjacent lane also
caused false target changes. Apply a 0.25-gain derivative filter and only predict
entry from within 2.8 m of the route (0.3 s lookahead). The stopping-distance guard
still covers all observed traffic within 4.5 m. Neither max braking nor the
collision/progress/freshness gates is relaxed. Rerun development before validation.

## Cooperative observation extension (development, before validation)

Six combined-fault trials still could not prove a non-connected vehicle's exit:
a nearer adjacent vehicle physically occluded its final lateral movement. This
is genuine missing information; absence remains insufficient. Connected neighbors
now share their OWN anonymous Radar scans (separate bounded `range_scan` schema,
8192 bytes, <=32 detections). No traffic-truth IDs are broadcast. The original
observer, ego sensing pose, sequence and measurement timestamp survive unchanged.
The receiver requires <=0.2 s age, per-observer replay checks and consistency with
the observer's fresh V2V pose. Original beacons remain unchanged/unauthenticated.
Cooperative scans are not relayed and do not extend any control TTL.

Only a unique geometric match to the last local track (<=2 s identity memory)
can contribute POSITIVE exit evidence; conflicting fresh views prohibit release.
Three distinct exit measurements are required. Peer detections are not copied
into the normal following-control input. Without direct following knowledge after
release, braking remains. Native peer scans must come from each peer's actual
Radar/GPS, with the same noise/miss model, never Supervisor object poses.
Python models a direct 50 ms cooperative datagram; native uses actual broadcast
and the declared receiver loss/jitter path. Every rejection/input is logged.
The data model and development source freeze distinguish this extra sensing
architecture from the previous local-Radar/own-state-V2V-only results.

Native development exposed association deadlocks from dormant, widening track
gates competing with fresh matches. Matching now prefers the <=0.5 s tier with
a 3 m positional gate (native return-centroid variation); only without a fresh
match does it use <=2 s identity coasting. A best match needs a >=1 m separation
from alternative costs; one-to-one conflicts still brake. Dormant memories do
not veto a clear fresh match indefinitely. This changes identity association,
not source control TTL or safety gates. Preserve the failed native development
and rerun the full Python/native development grids before fresh validation.

One corrected development trial still missed the unchanged progress requirement
(202.2 m versus 204.8 m required): relay slots spent on off-route traffic caused
intermittent source expiry. Keep the one-beacon/100 ms budget but prioritize
received beacons near the reference lane, with round-robin fairness within that
set; fall back to all origins if none are in-lane. This uses received positions
and the map, never scenario roles or target IDs. All vehicles still broadcast
their own states normally. Freshness and the progress threshold remain unchanged.
