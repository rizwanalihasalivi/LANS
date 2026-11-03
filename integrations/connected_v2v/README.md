# Connected V2V vehicles

Latest separate study: [fresh local range fallback and held-out recovery results](recovery/RESULTS.md).
It preserves the v1 source/evidence below and adds matched radar-ACC/V2V ablations.

This separate development module adds three requested capabilities: multi-vehicle
cooperative awareness, straight-road platoon following, and a native Webots
three-car radio/driver demo. It adapts the existing unified LANS packet inbox and
risk supervisor without editing the frozen controller, PPO campaigns or old
results. It does not promote the failed unified PPO campaign to Webots.

[Executed checks and limitations](RESULTS.md) · [Source/raw evidence bundle](evidence/connected-v2v-v1.zip)

## Message and discovery contract

Each vehicle publishes a bounded UTF-8 JSON beacon with `version: 1`, a vehicle
ID, a monotonically increasing sequence, the original observation timestamp in
seconds, and six SI-unit values: x, y, heading, longitudinal speed, lateral speed,
yaw rate. This is an application schema, not an ETSI CAM, DSRC or C-V2X stack.

- Each receiver has its own bounded registry and independent per-sender replay
  counters. New valid peers are discovered from messages; predeclared peers can
  be marked missing even before first contact. Capacity exhaustion is counted,
  not handled by silently removing an existing contact.
- Invalid IDs, reserved `ego` injection, future/expired timestamps, nonfinite
  states, duplicate JSON keys, replayed sequences and timestamp regressions are
  rejected. Receipt never replaces observation time. Local ego observations
  use a separate trusted sensing path.
- Contacts become stale after 0.4 s, matching the unchanged supervisor. A stale
  peer remains expected: a fresh message from another vehicle cannot hide its
  loss. Missing/stale registered traffic triggers bounded maximum braking through
  the existing supervisor. Fresh newer messages allow risk-based recovery.
- Peer departure and sender reboot are deliberately not inferred from silence.
  Replay counters persist for the endpoint lifetime; recovery from a sender's
  sequence reset requires a separately designed session/authentication protocol.
  A registry reset is not an automatic safety action.

IDs are claimed identities, not authenticated identities. This module does not
implement PKI, anti-Sybil protection or clock synchronization. Its timestamps
assume a common simulation clock. Undiscovered/non-connected obstacles still
need independent onboard perception; an empty registry is not evidence of a
clear road. A long blackout can keep a vehicle braking indefinitely until an
explicitly justified knowledge/membership update or fresh contact occurs.

## Use the existing pipeline

Attach before the pipeline receives its first local observation:

```python
from integrations.connected_v2v import V2VEndpoint
from integrations.unified_lans.controller import Pipeline
from integrations.unified_lans.physics import Route

pipe = Pipeline(Route(), mode='lqr')
radio = V2VEndpoint('vehicle-a', inbox=pipe.inbox,
                    expected_peers=['vehicle-b'],
                    max_packet_age_s=pipe.cfg.traffic_ttl)
# Every control tick, from local sensing:
radio.observe_local(local_state, observed_s, now)
# At the broadcast schedule:
payload = radio.publish(local_state, observed_s, now)
# For every received peer payload:
radio.receive(peer_payload, now)
radio.sync_expected(pipe)
decision = pipe.decide(now)
```

`sync_expected` owns the complete peer roster of its attached pipeline. It refuses
a different inbox, mismatched freshness limits, or unknown externally assigned
peers. It does not patch or automatically attach to another agent's controller.

## Python development demos

From `/workspace/LANS`, use the existing isolated checkout; no worktree is needed.
Python 3.10 and the current LANS environment already provide the dependencies.
Use NEW output directories; all runners refuse to overwrite an existing run.

```bash
source /workspace/lans-setup/env.sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q integrations/connected_v2v/tests

# 3 connected vehicles, or 4 after a late join; all use the unchanged LQR supervisor.
python -m integrations.connected_v2v --suite --seconds 3 --output results/my-v2v/awareness
python -m integrations.connected_v2v.verify results/my-v2v/awareness

# A leader and two followers, predecessor-state communication, 8 s per case.
python -m integrations.connected_v2v.platoon_demo --suite --seconds 8 --output results/my-v2v/platoon
python -m integrations.connected_v2v.verify results/my-v2v/platoon
```

Awareness cases: nominal, packet loss/jitter/duplication, one sender's blackout
and recovery, and a late-joining vehicle. The channel supports directed link
faults, range-at-transmission, delay/jitter, loss, duplicates, out-of-order arrival
and a bounded delivery queue. Delivery-time blackouts also drop queued messages.
Positions are used only by the channel's link-distance model and post-step scoring;
peer controller inputs come from received packets. Range is not re-evaluated
while a packet is in flight. No physical-layer contention, propagation model,
throughput guarantee or real-time timing is claimed.

The platoon uses predecessor-only unicast and a time-headway law:

`a = 0.35 * (bumper_gap - 6 - 1.2 * ego_speed) + 0.9 * relative_speed`

The unchanged risk supervisor can reduce that acceleration, and physical bounds
remain [-6, 2.5] m/s². Beacons are 10 Hz; control is 20 Hz. The lead-braking case
commands -3 m/s² between 2 and 3 s. The blackout case interrupts the lead-to-first-
follower link between 1 and 2.5 s. This is cooperative following with communicated
position/velocity, not acceleration-feedforward CACC or a demonstrated
string-stable platoon. There is no baseline superiority experiment in this stage.

The read-only auditor reconstructs every receiver history, original peer age,
discovery/rejection outcome, supervisor state, platoon command, actuator bounds
and shared-bicycle transition, and checks aggregate metrics and source hashes.
A negative test changes a raw trajectory and updates its file checksum: the
physics replay must still reject it. Shared-kernel replay is not independent
vehicle-model validation.

## Native Webots

The private runtime uses the repository's pinned archive/PROTO checksums and
signed Debian package metadata. It does not change a shared/system installation.

```bash
bash integrations/webots/install-private.sh
python -m integrations.connected_v2v.webots.run --case nominal --output results/my-v2v/webots-nominal
python -m integrations.connected_v2v.webots.run --case peer_blackout --output results/my-v2v/webots-blackout
# Read-only rechecks:
python -m integrations.connected_v2v.webots.verify results/my-v2v/webots-nominal
python -m integrations.connected_v2v.webots.verify results/my-v2v/webots-blackout
```

Each run creates its own world and three controller processes. Native `Emitter`
and `Receiver` devices use channel 7, 150 m range and 10 Hz broadcasts. Local GPS,
inertial heading, gyroscope and native speed measurements feed the controller;
it does not read other robots through Supervisor truth. Lateral speed is assumed
zero in this straight-road demo. Physics runs at 10 ms, control at 50 ms. Native
cruise-speed actuation is logged separately from the requested acceleration;
the Python acceleration integrator is not copied into Webots performance data.

Both cases include a leader brake request at 7-8 s. The blackout case mutes
follower-1's broadcasts at 5-6.5 s. An auditor replays received bytes at their
actual simulation receipt times, peer histories, decisions, steering bounds and
native speed-setpoint integration, and checks movement, recovery and a
conservative longitudinal gap proxy. It is not a contact-sensor safety audit,
hard real-time test, standardized radio validation or PPO transfer evaluation.

No extra training, paid service or API credential is needed. Existing unified
PPO promotion gates and reserved datasets remain untouched. New thesis-level
claims require longer predeclared matched trials, more seeds, realistic sensing,
perception of non-connected traffic and calibrated communication/vehicle models.
