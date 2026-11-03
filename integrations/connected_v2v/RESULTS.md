# Connected-V2V development validation — 3 November 2026

Subsequent separate experiment: [independent local sensing and recovery v2](recovery/RESULTS.md).
The v1 development results below remain unchanged.

Base: `60f7ecde47df70deaa3ee93d072f4fe5d53a9479`. All new code is isolated in
`integrations/connected_v2v/`. Existing unified controller/campaign source and
historical result files were not edited. No PPO training or reserved campaign
evaluation was started.

These are short development checks at one declared seed (`20261103`), not thesis
confirmation experiments or evidence of universal safety, string stability,
PPO superiority, 10 ms deadlines or main-campaign promotion.

## Tests and replay

- 61 new V2V/platoon tests passed, including multi-sender freshness, per-link
  faults, independent sequence counters, bounded queues/registries, discovery,
  replay rejection, predecessor loss/recovery and deliberately corrupted traces.
- 130 tests passed when combined with root, unified-integration, campaign,
  verifier and active v12 contracts. Dependency deprecation warnings remain.
- All eight Python cases passed source/hash, packet-history, control-contract,
  metric and shared-bicycle replay: **2,680 vehicle ticks / 1,419 delivery events**.
- Two fresh native Webots cases passed message-history and cooperative-command
  replay: **1,440 native vehicle samples / 1,410 radio receipt events**. These
  are native simulator results; they are not copied Python metrics.

Initial local tests caught a NumPy integer serialization issue in the new demo
summary. The counters were corrected to Python integers before final runs;
assertions and existing test expectations were not weakened. Early local runs
are separate from the final evidence below.

## Multi-vehicle cooperative awareness

3 s per case, 50 ms control, 100 ms beacons. Late join adds a fourth vehicle at
1 s. Every vehicle runs the unchanged unified LQR/risk supervisor.

| Case | Vehicle ticks | Radio delivery events | Missing/stale-peer braking ticks | Collision ticks | Corridor ticks |
|---|---:|---:|---:|---:|---:|
| Nominal | 180 | 180 | 0 | 0 | 0 |
| Loss/jitter/duplication | 180 | 176 | 7 | 0 | 0 |
| Peer blackout/recovery | 180 | 160 | 26 | 0 | 0 |
| Late join | 220 | 300 | 0 | 0 | 0 |

All receiver histories replay. The blacked-out peer remains in the expected
registry and becomes fresh again after newer messages arrive. Correlated
vehicle ticks are not independent episodes; delivery totals include duplicates.

## Straight-road cooperative following

8 s per case; one leader and two followers; 10 Hz predecessor-state unicast.
All listed gap measurements are the separate Python plant's true longitudinal
bumper-distance proxy. Nominal latency is 50 ms. Two startup fallback vehicle
ticks occur while the first predecessor messages are still in flight.

| Case | Minimum gap (m) | Follower spacing-error RMS (m) | Fallback vehicle ticks | Collision follower ticks |
|---|---:|---:|---:|---:|
| Nominal | 20.400 | 0.135 | 2 | 0 |
| Lead braking | 18.641 | 0.140 | 2 | 0 |
| Predecessor blackout | 15.109 | **8.140** | 26 | 0 |
| Loss/jitter/duplication | 20.400 | 0.137 | 2 | 0 |

The large blackout spacing error is retained: braking and packet recovery do
not establish good formation keeping. Communication freshness and smooth
platoon performance are separate requirements. No ACC/MPC/PPO baseline study,
string-amplification assessment, lane-changing platoon or stability proof ran.

## Native Webots convoy

Two separate 12 s generic-Car runs, each with three native controller processes,
local sensors and actual Webots Emitter/Receiver devices. Both include a leader
brake request at 7-8 s; the blackout case additionally mutes follower-1 at 5-6.5 s.

| Case | Native samples | Replayed radio receipts | Minimum longitudinal gap proxy (m) | Leader / follower-1 / follower-2 fallback samples |
|---|---:|---:|---:|---|
| Nominal | 720 | 720 | 16.559 | 0 / 1 / 1 |
| Peer blackout/recovery | 720 | 690 | 9.622 | 24 / 1 / 25 |

Each car discovered both other vehicles and moved more than 1 m. Follower-2
braked on missing predecessor broadcasts and resumed cooperative following
after fresh packets returned. The leader also braked conservatively when its
discovered follower went stale. This behavior follows the existing all-known-
traffic supervision policy; it is not optimized platoon coordination.

The longitudinal proxy stayed positive in these two runs. It is not a physical
contact/collision certificate. Native tire/servo/driver dynamics and ideal
GPS/IMU sensing differ from the Python bicycle. Wall-clock deadlines, real
V2X hardware, radio security, clock synchronization and full multi-lane traffic
remain unvalidated. Software rendering warnings were observed; native runs
completed and the audit required actual movement and radio delivery.

## Evidence and reproduction

Final current-instance outputs are under
`/workspace/LANS/results/connected-v2v-validation-v1/`:

- `awareness/`: four cases, raw ticks/messages, protocol/source hashes and replay.
- `platoon/`: four cases, raw gap/control/message histories and replay.
- `webots/nominal/` and `webots/peer-blackout/`: separate generated worlds,
  native controller/sensor/message logs, console output and verification files.

[The evidence bundle](evidence/connected-v2v-v1.zip) contains the final raw runs,
the new source/tests/docs and snapshots of the imported controller dependencies.
Its member hashes are in `MANIFEST.json`; its outer hash is in
[SHA256SUMS](evidence/SHA256SUMS). Webots binaries and dependency caches are not
vendored. Use the [README commands](README.md) with new output directories to
replicate; archived files and failed historical controller evidence stay intact.

This finishes the three development integrations. The next research stage is a
new declared platoon/communication benchmark with matched ACC/cooperative
baselines, longer braking/cut-in/dropout trials, multiple seeds, formation error,
progress, jerk and upstream/downstream disturbance amplification. Its acceptance
criteria and untouched confirmation cases must be fixed before seeing outcomes.
