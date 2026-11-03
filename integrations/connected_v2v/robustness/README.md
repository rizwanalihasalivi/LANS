# Broader following, fallible perception and physical-road validation

This separate stage extends [autonomous target selection](../autonomy/README.md).
It preserves the previous controllers, experiments and evidence. Final thesis
comparison/benchmarking remains on hold; these are new development and validation
trials of the extended observation architecture.

The prepared native operating profile explicitly uses **300 m communication**.
The separately retained 150 m fresh cohort achieved 35/36 recovery/progress passes
with zero sampled safety violations; one head vehicle left all available radio
paths. It is not advertised as full recovery at 150 m. The coverage-only adapter
and new independent cohort are specified in [COVERAGE_PROTOCOL.md](COVERAGE_PROTOCOL.md).

## What changes

- `RobustFollower` never treats missed detections as proof of departure. It needs
  three distinct positive exit measurements, or retains the predecessor and brakes.
  Fresh sources must agree. An initially unknown empty road does not grant cruise.
- Local tracking prioritizes unambiguous fresh geometry; dormant uncertainty gates
  cannot deadlock a clear fresh match. Two-second identity memory supports matching
  a NEW measurement, not extending its control lifetime. Ambiguity/capacity exhaustion
  still brakes. A unique matched radio identity can promote the same anonymous track.
- Connected neighbors forward at most one accepted ORIGINAL beacon per 100 ms,
  at most 0.25 s old, prioritizing the reference lane and rotating within that set.
  IDs, sequence numbers and observation stamps are not rewritten. Direct links are
  still 150 m; the selector may use fresh relayed state out to 300 m. This is a
  simulated application relay, not a standardized radio or capacity claim.
- A separate bounded `range_scan` message shares a neighbor's own anonymous radar
  detections and sensing pose. No non-connected vehicle identity is invented.
  Freshness is 0.2 s, with independent per-observer replay and fresh V2V-pose
  consistency checks. Only a unique match to recent local track memory contributes
  positive exit evidence. Peer detections are not substituted into the normal
  following-control state. Cooperative scans are not relayed.

The nominal formation gains and physical requested bounds are unchanged. Normal
following still requires fresh ego (0.2 s) and local radar (0.2 s) or V2V (0.4 s).
The stopping-distance guard covers observed forward traffic within 4.5 m of the
reference route, including adjacent lanes. Blind/ambiguous selection requests
maximum braking. Original source ages survive every switch and relay.

## Fixtures and independent cohorts

Python: 32 s, 20 Hz control, eight profiles, speeds 8/12/16 m/s. The ego uses the
shared bicycle plant; NPC paths generate sensor observations and scoring truth.
Detection order is shuffled. Sensors include oriented-box line-of-sight occlusion,
Gaussian range/bearing/rate noise, independent misses, a 1 s burst and latency.
Communication includes loss/jitter/duplicates and V2V/dual blackout. Miss labels
and scenario switch times never enter the controller.

Webots: 35 s, real physical curved/straight two-lane road ribbons, real native
Radar/GPS/IMU/Gyro and Emitter/Receiver, and measured body lateral velocity. Native
curved radius is 600 m (Python uses 800 m). Dense cases contain eight physical
Cars; others contain three. NPCs follow their own GPS and scripted routes. The ego
does not read other robots through Supervisor truth. Each connected observer
actually samples its own Radar; software misses/latency act on those raw returns.
The declared 2.5 m native ego-body mask is a blind region, not clear-road evidence.

Development and fresh validation use different predeclared seeds, fixed before
opening validation. Source freezes and gates prevent silent changes/reuse. Every
failed/invalid development attempt is retained; exact amendments are in
[PROTOCOL.md](PROTOCOL.md). [RESULTS.md](RESULTS.md) records the completed cohorts,
including progress, stopping, spacing and censored stable-return observations.

## Reproduce without changing old evidence

Use the existing isolated `/workspace/LANS` checkout; do not create a worktree
unless requested. No training, paid service or new secret is required.

```bash
cd /workspace/LANS
source /workspace/lans-setup/env.sh
python -m pytest -q integrations/connected_v2v

# All roots must be NEW. Never overwrite or silently resume partial outputs.
python -m integrations.connected_v2v.robustness.study \
  --output results/new-robustness --stage development
# Only after Python development passes and source remains frozen:
python -m integrations.connected_v2v.robustness.study \
  --output results/new-robustness --stage validation
# Explicit 300 m operating profile, without editing the original templates:
python -m integrations.connected_v2v.robustness.coverage \
  --python results/new-robustness --output results/new-robustness-native --stage development
# Only after native development also passes:
python -m integrations.connected_v2v.robustness.coverage \
  --python results/new-robustness --output results/new-robustness-native --stage validation

python -m integrations.connected_v2v.robustness.audit \
  --python results/new-robustness --native results/new-robustness-native
python -m integrations.connected_v2v.robustness.verify_inputs results/new-robustness --stage validation
python -m integrations.connected_v2v.robustness.report \
  --python results/new-robustness --native results/new-robustness-native --output results/new-robustness-report
python -m integrations.connected_v2v.robustness.negative_checks \
  --python results/new-robustness --native results/new-robustness-native
```

The original `robustness.native` launcher retains the 150 m diagnostic profile;
it is a separate experiment with the original seed cohort and operating limit.

Python uses three independent worker processes, native uses two isolated Webots
processes with separate outputs/displays. The native runner verifies the pinned
archive/PROTO checksums before launch. Use supported execution permission for X11
sockets when required by the shell sandbox; preserve TLS/signature/checksum checks.
No process needs to persist between tasks/publication. Raw source/receiver/control
replay, cooperative sensor regeneration and the stdlib scorer are distinct checks.

## Limits that remain part of the model

Known-route geometry, common simulation clocks and approximately route-aligned
traffic remain assumptions. IDs and sensing claims are unauthenticated; this is
not PKI, an adversarial-perception test or an implemented C-V2X/DSRC stack. Gaussian
sensor errors and simple ray occlusion are finite model choices, not a learned
real-world perception system. Local poses are idealized sensing positions.

A genuinely unobservable non-connected target may require an indefinite safe stop.
Neighbor observations help only where an actual fresh view and radio path exist.
Target reassociation is not nominal headway settling; the conservative adjacent
traffic guard can retain large spacing to the head vehicle. Requested acceleration
bounds do not assert matching native speed-servo acceleration. Sampled box checks
do not prove continuous-time or physical-world collision-free safety, string
stability, arbitrary geometry or real-time deadlines.

Cloud installation/start instructions are saved separately in the environment
draft. Publishing/restoring that snapshot is a product UI action, not Git push.
