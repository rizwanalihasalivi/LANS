# Formation recovery v3 — 3 November 2026

Base: `43679a5b`. One analytically chosen fresh-data feedback candidate passed
all frozen development and held-out gates. Separate native factorial tests
identify the follower speed-cap adapter mismatch. Blind-phase braking is
preserved; unknown traffic is never replaced with fabricated fresh knowledge.

[Protocol](PROTOCOL.md) · [Run instructions](README.md) · [Figure](evidence/formation-v3.png) · [PDF](evidence/formation-v3.pdf)

## What changed

For fixed-headway error e and predecessor relative speed dv, the same law
`a=kp*e+kv*dv` now has one candidate kp=0.64, kv=0.832, derived from nominal
double poles -0.8 /s. Baseline remains kp=0.35, kv=0.9. This nominal calculation
is not a nonlinear/delayed/string-stability proof. Both variants retain 6 m
standstill gap, 1.2 s headway, v2 sensing/source agreement, original timestamps,
0.4 s V2V / 0.2 s range TTL and [-6,2.5] m/s² requested acceleration limits.
Both variants receive the same cruise+8 m/s follower speed envelope; leaders
remain at cruise. No learning, parameter search, target-seed selection or
post-outcome criterion change occurred.

## Held-out Python results

144 development + 144 confirmation episodes, **518,400 vehicle ticks**.
Each stage has three independent seeds, three speeds and eight scenario
classes, comparing both variants with matched initial states/noise/faults.
Confirmation uses new seeds 7101/7102/7103 and events shifted by 0.15 s.
All receiver/control/physics replays and an independent standard-library scoring
checker passed; a corrupted summary was rejected.

| Recovery event | Baseline settling | New settling | Reduction |
|---|---:|---:|---:|
| Dual-sensor blackout, after event ends | 11.10 s | **7.70 s** | **30.63%** |
| Cut-out predecessor handover | 10.73 s | **6.85 s** | **36.18%** |

Settling requires BOTH followers within 1 m fixed-headway error for at least
2 s, fresh source knowledge, and no later error violation in that segment.
Neither baseline nor candidate was censored at 30 s in the primary events.
The three-seed-cluster bootstrap bounds passed, but some intervals collapse
because all clusters share a 50 ms quantized event time. A zero-width bootstrap
interval does NOT establish zero uncertainty or generalization to new traffic.

The observation horizon is 30 s to see settling; fixed FIRST-20-second spacing
RMS below prevents apparent improvement merely by averaging over a longer run:

| Scenario | Baseline RMS (m) | New RMS (m) |
|---|---:|---:|
| nominal | 0.0882 | 0.0668 |
| leader_brake | 0.0914 | 0.0714 |
| v2v_blackout | 0.0882 | 0.0667 |
| radar_blackout | 0.0882 | 0.0668 |
| dual_blackout | 6.2542 | 5.9924 |
| loss_jitter | 0.0886 | 0.0674 |
| ego_blackout | 0.6337 | 0.4822 |
| cut_in | 8.2475 | 7.8721 |

Every frozen gate passed: at least 20% settling gains, first-20 target RMS
nonregression, nominal nonregression, >=99% matched follower progress in EACH
cell at both horizons, and the original 5%+0.1 command-jerk budget. Candidate
collision/corridor/stale-source/blind-brake/actuator/speed-envelope violations
were all zero. Command jerk mean changed from 7.7962
to 7.8757 m/s³, so faster response has a small
measured smoothness cost within the frozen budget. Maximum candidate speed on
confirmation was 23.6802 m/s (scenario-dependent envelope <=cruise+8).
These are finite-model observations, not vehicle-safety guarantees.

**The blind phase is not solved:** dual-blackout first-20 RMS remains about
6 m. Braking without fresh knowledge is retained. Cut-in/out first-20 RMS
also remains about 7.9 m because imposed target changes create an abrupt gap
reference and bounded acceleration cannot close that gap instantly. This work
improves subsequent recovery, not autonomous cut-in recognition or all errors.

## Native adapter correction and factorial attribution

The old native adapter clipped ALL speed setpoints to the leader's 8 m/s,
preventing followers from catching up to a large gap. The new adapter keeps
leaders at 8 m/s and allows followers a bounded recovery setpoint up to 16 m/s.
This is compared separately from feedback gains: 2 laws x 2 adapters x 4 cases,
**16 valid 30 s runs / 28,800 native samples**,
with native Radar and Emitter/Receiver and all source/control/pose audits passed.
Each native cell has one world seed 42; there is no native multi-seed interval.

| Case | Law | Adapter | First-20 RMS (m) | Final-5 RMS (m) |
|---|---|---|---:|---:|
| nominal | baseline | legacy | 5.2668 | 3.1012 |
| nominal | damped | legacy | 5.3495 | 3.4188 |
| nominal | baseline | recovery | 4.3439 | 0.0136 |
| nominal | damped | recovery | 4.2199 | 0.0161 |
| v2v_blackout | baseline | legacy | 5.2668 | 3.1012 |
| v2v_blackout | damped | legacy | 5.3495 | 3.4188 |
| v2v_blackout | baseline | recovery | 4.3439 | 0.0136 |
| v2v_blackout | damped | recovery | 4.2199 | 0.0161 |
| radar_blackout | baseline | legacy | 5.2668 | 3.1012 |
| radar_blackout | damped | legacy | 5.3495 | 3.4188 |
| radar_blackout | baseline | recovery | 4.3432 | 0.0136 |
| radar_blackout | damped | recovery | 4.2197 | 0.0161 |
| dual_blackout | baseline | legacy | 7.6117 | 6.8622 |
| dual_blackout | damped | legacy | 7.4866 | 6.7084 |
| dual_blackout | baseline | recovery | 5.1739 | 0.0190 |
| dual_blackout | damped | recovery | 4.7229 | 0.0161 |

On the native dual-blackout case, correcting the cap with OLD gains reduces
first-20 RMS by **32.03%**. With the corrected adapter held fixed,
the new gains add a separately measured **8.72%** reduction. Do not
attribute the combined effect to gains alone. Final-5 RMS falls from
6.8622 m (old law/cap) to
0.0161 m (new law/recovery cap).

Native acceleration checks bound the REQUESTED commands and setpoints. The
speed servo/tire response differs: maximum observed speed-derived acceleration
was 2.5079 m/s², slightly above the requested +2.5 m/s² ceiling. No
physical acceleration hard-bound certification is claimed. Height, tilt, forward
heading, corridor and road-bound checks now validate every native sample.
Positive gap proxies are not a contact-sensor collision certificate.

## Fixture defect found and corrected

The initial 30 s native fixture reused a 200 m road centered at x=50 (bounds
[-50,150]). Cars crossed its end; late headings flipped and messages disappeared.
Those **16 short-road runs are invalid as on-road performance evidence** even
though their old longitudinal-gap-only proxy checks said passed. Their worlds,
source snapshots and raw outcomes are retained with an invalidation record.

Only the flat-road extent was corrected to [-500,1500], with added explicit
GPS height/attitude/map/corridor guards. The SAME 16 controller/adapter cases
were rerun with unchanged gains, sensor models, seed, fault timing and bounds.
Only these valid long-road runs enter the table. Python outcomes were unaffected.
This was a fixture correction, not relaxed criteria or retuning to a preferred result.

## Checks, evidence and remaining scope

158 tests passed in the combined regression command; the updated four native
fixture tests passed separately (one repeat plus three new negative pose cases):
**161 distinct tests passed**. Scientific source freeze:
`ea76cdcf9afa9dc87653aafad53f4fd7e147d641f708c8cc77525478a3721160`. Controller/model replay shares the original
kernels; the separate stdlib checker independently recomputes first-20/full
metrics, constraints, progress and settling/censoring but is not a new simulator.

[Python/source bundle](evidence/formation-python-v3.zip) and
[native bundle including invalid fixture diagnostics](evidence/formation-native-v3.zip)
retain all runs, hashes, protocols, tests, source snapshots and figures.
[Outer checksums](evidence/SHA256SUMS) and each ZIP's MANIFEST.json verify integrity.
Current-instance data roots are `results/connected-v2v-formation-v3/`,
`results/connected-v2v-formation-native-v3/` (INVALID short road), and
`results/connected-v2v-formation-native-v3-longroad/` (VALID native factorial).

V1/v2 sources/evidence and the main PPO/controller track remain unchanged.
Membership/target identity is still scripted; native cut-in transfer, general
multi-lane/unconnected perception, string stability, real radio/time-sync,
wall-clock deadlines and physical validation remain open. The next stage must
declare new data/criteria rather than retune on these held-out results.
