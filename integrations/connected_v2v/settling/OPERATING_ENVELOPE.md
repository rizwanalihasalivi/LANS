# 150 m recovery and formation operating envelope

The direct radio range stays150 m in generated worlds, native setRange and Python
links. A relayed head can be farther away only through actual individual hops;
original observation time and replay counters are preserved. No300 m adapter is
used. This is a simulator link parameter, not an RF link-budget guarantee.

## Supported research configuration

- One connected head and observed ego member, with three or eight total actors.
  Non-connected actors do not transmit or relay and their NPC control does not use
  V2V. NPC maneuvers are fixture scripts; ego target choice is observation-driven.
- Two lanes; known straight/circular route. Native curved radius600 m; Python800 m.
  70 s episodes, ego/head cruise8/12 m/s native and8/12/16 m/s Python.
  Native recovery setpoints are capped at16 m/s and actual planar speed is
  qualified at most16.5 m/s from10 ms records. This follows a preserved steering
  failure near18.5–18.75 m/s; arbitrary-speed steering stability is not proved. The road is
  physically extended and steering uses route-normal errors on full arcs.
  Station projection uses the principal atan2 branch; the tested horizon stays
  below a half-turn. Full laps and route junctions need separate station unwrapping.
- Head initially70±2 m ahead, intruder36±2 m in Python /45±2 m native. Dense actors
  retain their original offsets. Loss/delay/duplicate/radar noise, misses, occlusion,
  burst and V2V/dual blackout profiles are specified by the archived case config.
- Head reduces its cruise goal by at most4 m/s when received member position shows
  gap>60 m, or when member information is stale. The goal uses own state and received
  beacons, not other-robot Supervisor state or a target/maneuver timeline.
- Relay role priority2:1 head/member under one forwarded packet/100 ms and maximum
  original age0.25 s. Role membership configures routing, not ego's predecessor.
  Normal following still requires original-age≤0.2 s radar or≤0.4 s radio.
- Conservative approach guarding remains. Positive observed departure enables
  lane-aware catch-up. A new measured cut-in restores approach mode; two seconds
  of measured spacing/speed settling ends catch-up. Predicted lane entry can brake
  immediately but does not by itself establish target membership.
- Near-boundary anonymous entry needs two distinct measurements, unless strongly
  inside the lane. Unique fresh peer chains can retain an exit-association anchor;
  they do not refresh local/radio timestamps or become nominal following state.

## Necessary recovery condition

Every actual hop must be within150 m at transmission, every forwarded original
observation must be at most0.25 s old, and end-to-end age must still fit the0.4 s
nominal V2V lifetime (or0.2 s for contributing radar/peer observations). Link
availability alone does not bound queue/loss delay. A single briefly fresh path
is insufficient for the40-tick stable-return gate. No general finite settling
time or universal connectivity invariant is proved. Because pacing has a positive
cruise-minus4 m/s floor here, a sufficiently long member stop can still break all
paths; outside-envelope recovery delay can be unbounded.

A fresh local observation or actual original-age radio path to the required
vehicle must become available. Pacing/routing improve retention; they cannot
manufacture knowledge after all sensing/communication paths are gone. Unobservable
or physically unavoidable cut-ins are outside a guaranteed recovery claim.

When selected knowledge is unavailable, ego marks `knowledge_unavailable`, retains
identity rather than inferring departure from silence, and requests maximum braking.
The deliberately unreachable Python/native diagnostics keep their ordinary recovery
gate FALSE and are labelled OUTSIDE_CONNECTIVITY_ENVELOPE. Their expected safe stop
is not included as a normal recovery success.

The unreachable Python diagnostic starts at12 m/s and brakes. The native fixture
starts at rest and inhibits launch; it is a cold-start fail-safe check, not a
moving-vehicle stopping experiment. Moving native loss/braking is exercised in
the ordinary blackout profiles and qualified by their actual motion records.

## What “settled” means

The declared70 s cohort requires continuous2 s correct fresh head return. These
windows mean40 consecutive20 Hz control ticks with no failed sample. This is a
sampled association/performance property, not a continuous-time perception theorem.
The separate physical footprint certificate covers intersample time under its bounds.
Settling
onset must occur by60 s and be confirmed for2 s: headway error≤2 m and relative
speed error≤0.5 m/s at every confirmation sample. Reported delay is the START of
that confirmation window after cut-out, not its end. This clarifies the code's
window-start convention without changing gates or stored outcomes.

During the final5 s, require headway-error RMS≤2 m,max absolute≤5 m,relative-speed
RMS≤0.5 m/s,correct fresh head association≥95%,and head cruise-speed RMS≤0.5 m/s.
Progress must exceed60% of cruise distance. These gates prevent passing by simply
stopping or permanently slowing the entire formation. Whole-episode correct-target
spacing RMS and stopped time are also retained; they must not be compared directly
to the new final-window RMS as a causal improvement percentage.

Spacing uses a declared nominal4.6 m reference vehicle length: route-station
separation minus4.6 m. The independent footprint theorem uses its larger enclosing
body rectangle; a nominal headway error is not a physical clearance certificate.

## Evidence boundaries

Strict frozen development and genuinely new validation seeds support empirical
claims only in this configuration. Gaussian radar errors remain unbounded in
theory. The [2-D proof](THEORY2D.md) certifies completed trajectories continuously
under declared pose/body/acceleration/yaw bounds; it does not prove all future
actions of the full controller. Real-time execution, physical hardware, arbitrary
traffic, authentication, comfort and string stability are not established.

The older150 m35/36 cohort and all exploratory/frozen failures remain preserved.
They are not relabeled. Final thesis benchmarking and published-method comparisons
remain on hold.

Initial broad approach guarding is retained. After an observed cut-in, three
distinct fresh unblocked source observations establish following before allowing
the lane-aware guard; repeated ticks on one stamp do not count. New target
selection resets that confirmation. This prevents adjacent traffic from causing
unnecessary prolonged stops after the actual predecessor has been admitted.
Missing target knowledge still brakes. All amendments/failures are in PROTOCOL.md.
