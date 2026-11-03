# Observation-driven target selection (development)

This separate module adds autonomous predecessor selection to the v3 formation
law. The scenario does **not** issue predecessor IDs or membership changes.
Only ego sensing, accepted V2V bytes, anonymous radar returns and the known route
map enter the controller. Final thesis comparison and benchmarking remain on hold.

`AutonomousFollower(endpoint, road=Road(), speed=12.)` wraps the unchanged v3
feedback law. Feed local state through `endpoint.observe_local`, raw messages
through `endpoint.receive`, and radar scans through `control.observe_scan`.
Call `control.decide(now)` for a bounded SI `Command` and a decision record.
The native adapter demonstrates the complete interface.

Radar `Detection` supplies centre range in metres, left-positive bearing in
radians and radial relative speed in m/s. A `Scan` includes its original timestamp,
monotonic sequence, sensing-time ego state, all returns and an explicit health/
coverage flag. It contains no traffic labels. Association uses bounded local tracks
and unique position/speed matches to fresh V2V observations. Unconnected objects
keep anonymous local track identities. Radio and radar replay checks survive
target switches; receipt does not refresh observation time.

A new closer in-lane obstacle takes effect immediately when current ordering is
observed. A farther target or clear road needs three distinct frames of positive
departure/clearance evidence. Silence and the previous target's historical gap
cannot establish current ordering or departure. Blind knowledge, stale ego,
ambiguous association or capacity exhaustion causes braking. A stopping-distance
guard considers **all** observed forward traffic within 4.5 m of the route,
including adjacent lanes, before allowing catch-up. It is deliberately conservative.

## Run in the prepared environment

Use the existing isolated checkout; do not create a worktree unless requested.
The environment installation/start instructions are also saved in its draft.

```bash
cd /workspace/LANS
source /workspace/lans-setup/env.sh
python -m pytest -q integrations/connected_v2v

# Every output must be new; runners refuse to overwrite old evidence.
python -m integrations.connected_v2v.autonomy.study --output results/new-autonomy-python
python -m integrations.connected_v2v.autonomy.native \
  --study results/new-autonomy-python --output results/new-autonomy-native
python -m integrations.connected_v2v.autonomy.audit \
  --python results/new-autonomy-python --native results/new-autonomy-native
```

The native runner checks the Python development gate and unchanged Python runtime
dependencies, verifies the pinned Webots archive/PROTO checksums, then freezes its
own source. Native adapters/tests are frozen separately because Python episodes
do not import them. No old confirmation gate/data is opened. Webots processes and
their Xvfb displays start per run and terminate; no persistent server is required.
Use the supported execution permission for X11 sockets when the shell sandbox
blocks them, preserving the wrapper and runtime verification.

Python: eight development cases × five seeds, 20 s each. They cover connected/
non-connected cut-in/out, a 500 m radius curve, dense two-lane traffic, V2V-only
and dual-source blackout, packet loss/jitter/duplicates and 150 ms delayed radar.
The ego uses the shared bicycle plant; NPC paths and idealized sensor generation
are simulation fixtures. Returns are shuffled to prevent order conveying identity.

Webots: four cases × three seeds, 30 s each, three physical generic Cars and a
2,000 m road. The intervening vehicle changes lanes using its own sensors and a
scripted NPC route. The follower discovers/changes targets independently. Cases
cover connected, non-connected, V2V blackout and dual blackout. Native sensing
uses Radar/GPS/IMU/Gyro and native Emitter/Receiver bytes. Radar clockwise bearings
are converted to SI left-positive bearings; GPS velocity supplies body lateral
speed. Invalid initial radial speeds mark scans incomplete instead of granting
clear-road knowledge or crashing. The 0.1 m range correction retains the original
GPS/radar-to-box-centre calibration. Saturated 0.5 m self returns are excluded.

Replay rebuilds accepted inputs, target selection, source arbitration and commands.
Python replay also checks sensor generation, NPC paths and bicycle transitions.
The separate `audit.py` uses only the standard library, importing no controller,
plant or scoring helpers; it recomputes sampled box overlaps, requested command
bounds, freshness, blind braking and progress, checks source freezes and matches
native wire states to sender traces. It is an independent scoring implementation,
not independent validation of vehicle dynamics or the perception assumptions.

## Scope and remaining work

This is a development implementation on a known route with bounded traffic and
shared simulation clocks. Radar reconstruction assumes approximately route-aligned
traffic. A complete scan assumes the declared corridor is observable; this is not
a real-world missed-detection/occlusion guarantee. Track capacity is 32 for the
endpoint lifetime and exhaustion fails closed. V2V IDs remain unauthenticated.

Curved and dense scenarios have Python development coverage. Native curved roads,
dense traffic, wider speed/braking distributions, realistic perception/occlusion,
more independent seeds and confirmation experiments remain pending. The existing
v1/v2/v3 source and evidence remain available for their original scoped claims.
See [executed results](RESULTS.md) for exact retained runs and failures.
