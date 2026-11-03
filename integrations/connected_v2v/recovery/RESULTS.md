# Recovery and independent-sensing results — 3 November 2026

Subsequent separate stage: [formation recovery v3 and native adapter correction](../formation/RESULTS.md).
The v2 controller, protocol and result body below remain unchanged.

The one frozen candidate passed all predeclared development and held-out checks.
It bridges V2V loss using independently fresh local range/range-rate sensing.
This is additional sensing and validated source arbitration, **not a PPO gain**,
an equal-information controller advantage, a new safety theorem, or autonomous
vehicle identification. The v1 following law, gains, limits and V2V TTL are unchanged.

[Protocol](PROTOCOL.md) · [Run instructions](README.md) · [Figure](evidence/recovery-v2.png) · [PDF](evidence/recovery-v2.pdf)

## Original defect diagnosis and regression fixture

The original 8 s blackout was reproduced with **zero physical-state discrepancy**
and identical per-tick commands against archived v1. Blind maximum braking drops
the follower from about 12 to 5 m/s; the leader continues, and acceleration-limited
recovery cannot instantly restore the gap. Sensor freshness or actuator limits
were not relaxed to obtain a desired number.

On this same regression fixture, spacing RMS was
**8.140370 m V2V-only**, **0.138518 m radar-ACC**,
and **0.133665 m combined sensing**. This is a diagnostic reproduction,
not an extra selected seed or held-out experiment.

## Frozen Python study

216 development + 216 confirmation episodes; **518,400 vehicle ticks**.
Each stage has 3 independent seed clusters, 3 speeds and 8 scenarios, with all
three methods evaluated on matched inputs. Confirmation uses new seeds and
faults shifted 0.15 s. All receiver/control/physics replay audits passed and
raw episode hashes were checked again during sealing.

Development V2V-blackout spacing gain: **98.2915%**.
Held-out gain: **98.5225%**, descriptive 95% seed-cluster interval
**[97.9890%, 98.8384%]**.
Only three independent seed clusters underpin these intervals; correlated
speeds/time steps are not additional independent trials or broad-road evidence.

Held-out mean follower spacing RMS, in meters:

| Scenario | V2V only | Range ACC | Range + V2V |
|---|---:|---:|---:|
| nominal | 0.0923 | 0.0955 | 0.0923 |
| leader_brake | 0.0958 | 0.0988 | 0.0958 |
| v2v_blackout | 6.2694 | 0.0955 | 0.0926 |
| radar_blackout | 0.0923 | 7.2385 | 0.0923 |
| dual_blackout | 6.2694 | 7.2385 | 6.2686 |
| loss_jitter | 0.4293 | 0.0955 | 0.0948 |
| ego_blackout | 0.7249 | 0.8834 | 0.6225 |
| cut_in | 8.2380 | 9.0009 | 8.2380 |

All ten frozen checks passed in both stages: blackout gain/interval, radar-ACC
noninferiority, nominal nonregression, no observed collision/corridor violation,
fresh-source and actuator integrity, at least 99% matched follower progress in
every cell, and the declared command-jerk budget. Fusion's minimum bumper-gap
proxy on confirmation was **4.1096 m**.
The jerk metric differentiates requested/applied acceleration commands; stops
and physical actuator filtering can make executed vehicle jerk different.

A separate standard-library checker (importing no controller, simulation or
report helper) independently reconstructed spacing, progress, gap, collision,
freshness, bounds and command-jerk metrics for all **432 episodes / 518,400 vehicle
ticks**. A deliberately altered summary was rejected. It also reports executed
speed-derived jerk as a posthoc diagnostic, without replacing any frozen gate.
Unit verification comprised 146 combined root/V2V/recovery tests plus one
native-adapter assembly test: **147 distinct tests passed** in separate commands.

Sources are independently validated before arbitration. Original timestamps and
replay watermarks remain intact. Both unavailable or inconsistent fresh sources
still trigger braking; there is no stale-packet acceptance, TTL increase, extra
authority, best-seed selection, added training or post-outcome threshold change.

Confirmation execution used three independent logical-time processes. Before
confirmation, two complete episodes/summary records reproduced serial raw-data
SHA-256 exactly. The execution-only launcher, its record and source are archived.
Native-only template assembly initially caught an unmatched parenthesis; it was
corrected before native trials, without changing the frozen scientific controller.

## Conditional native Radar transfer

Both Python gates passed before twelve native runs opened. **8,640 native
vehicle samples** and **8,460 radio receipts** were replayed, including actual
native Radar range/radial-speed and Emitter/Receiver messages. Each run used the
same frozen FusionFollower class, with method masking, original gains/limits
and the existing generic-Car driver. All native integration/proxy checks passed.
Each native case/method has one run at world seed 42; native uncertainty across
seeds was not measured.

| Native case | V2V only RMS (m) | Range ACC RMS (m) | Range + V2V RMS (m) |
|---|---:|---:|---:|
| nominal | 6.3215 | 6.6504 | 6.3103 |
| v2v_blackout | 8.6015 | 6.6504 | 6.3103 |
| radar_blackout | 6.3215 | 9.9851 | 6.3103 |
| dual_blackout | 8.6015 | 9.9851 | 8.0726 |

The native V2V-blackout reduction is **26.6371%**, measured independently;
the Python 98% figure is not copied into Webots. Cars start from rest with the
native 8 m/s cruise-speed cap, unlike the Python steady-speed initial states.
Native sensing cadence/phases, tires and speed servo also differ. Initial gaps
and speed saturation leave substantial absolute spacing error even in nominal
runs; passing this integration check does not establish excellent formation keeping.

## Remaining limitations and next work

- **Both sources lost:** braking remains mandatory and confirmation spacing RMS
  remains about 6.27 m. Independent sensing bridges a communication outage;
  it cannot supply knowledge when perception also fails.
- **Cut-in/out:** confirmation RMS remains about 8.24 m. Membership changes and
  target association are scripted common inputs, not an autonomous detection or
  authenticated membership result. Physical cut-in safety is not certified.
- Straight-road range reconstruction assumes aligned heading, ideal local
  GPS/state and bounded Python range/rate errors. Native Radar has its own
  Gaussian noise and a declared target-box/GPS geometric offset. No general
  multi-lane perception, mixed unconnected traffic, real V2X hardware, time-sync,
  security, wall-clock scheduling or string stability is validated here.
- The radar-ACC baseline is the same time-headway law with local sensing, not
  a tuned commercial system or matched published robust MPC implementation.
- No main unified PPO controller, training campaign or its reserved data changed.
  Integration with the other controller-development track remains a separate task.

The next stage should address constrained formation recovery, autonomous target
association/cut-in handling, and downstream disturbance amplification with a new
frozen protocol. Do not keep extending these seeds or retuning on confirmation.

## Evidence

Base source commit: `d5cc9efd35316fb40d18127a71f87c046997eea6`.
Scientific source/protocol freeze SHA-256: `18d4b9977d0320b703f1abdcc66fd0a93b49330665878ef9e732830d2e495fa0`.
Current-instance results: `results/connected-v2v-recovery-v2/` and
`results/connected-v2v-recovery-native-v2/`. The immutable v1 source/evidence remains
unchanged. [The new evidence bundle](evidence/recovery-v2.zip) includes every
episode/native run, protocols, frozen/source snapshots, audits and execution
records. Its member manifest and [outer hashes](evidence/SHA256SUMS) support integrity
checks. Reports/figures were generated after evaluation and did not select a controller.
