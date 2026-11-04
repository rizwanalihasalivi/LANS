# Predeclared settling, 150 m and continuous 2-D trace study

Date: 4 November 2026 (Asia/Shanghai). Parent `164938e9`. This is a new integrated
development/validation cycle; prior source/evidence remains frozen. Final thesis
benchmarking and published-controller comparisons remain on hold.

## Changes and exploratory failures retained

An exploratory always-narrow lateral guard produced cut-in collisions and failed
all eight Python probes; native noisy/non-connected recovery also lost its path.
Those unfrozen exploratory traces remain in settling-probe-v1 and
settling-native-probe-v1. They are failures, not final evidence. The v2 exploratory
policy passed eight Python and two native probes, before the stronger final gates.

The final candidate keeps conservative approach guarding, enters lane-aware
catch-up only on distinct positive exit observations, and exits recovery after
two seconds of observed spacing/speed settling. A newly detected cut-in restores
the normal conservative mode. The lane-aware preview is 0.6 s with a declared
3 m/s² lateral uncertainty allowance; it is not a guarantee against arbitrary
inadmissible hidden intrusions. Steering uses route-normal errors on full circular
arcs rather than a short forward-Cartesian road graph.

Leader pacing is causal: own state plus received member beacons, never simulator
truth. At a member gap above60 m, reduce goal by at most4 m/s; missing beacons use
the same bounded reduction. No time/target-script trigger is supplied to ego.
The initial head/intruder geometry and all noise/loss/maneuvers remain as previously
defined; the leader now has actual closed-loop pacing dynamics. Python traffic
replay reconstructs those dynamics from the accepted message stream. Native NPCs
use their own sensors. Pacing is part of the new architecture, not an isolated
guard-performance attribution.

Development amendment before opening validation: the first frozen72-run grid
passed71 but combined/16/6121 lost head refresh through congested relays. Preserve
that complete grid/source as settling-v1. The revised candidate prioritizes
configured head/member ORIGINAL beacons2:1 under the same one-forward/100 ms,
0.25 s original-age budget, and starts pacing at60 m instead of80 m. This does not
increase radio range or supply a scripted ego target. A new development root is
required; the declared fresh validation seeds have not been opened.

The relay probe additionally exposed loss of positive exit evidence when the
local anonymous track was older than2 s although a neighbor kept observing the
same object. A uniquely matched fresh peer observation now anchors the next peer
association (maximum0.5 s association gap). Only original-age≤0.2 s measurements
contribute exit evidence. The anchor never becomes a nominal-following packet or
extends a sensor TTL; silence still supplies no departure evidence. Preserve the
failed relay probe before this amendment.

The subsequent anchor probe obtained positive exit but exposed a noisy speculative
re-entry of an adjacent anonymous track, then lost that false predecessor. Target
membership now uses measured current in-lane position, not lateral prediction.
Near-boundary anonymous entry requires two distinct frames unless strongly inside
the lane (|d|≤1.3 m). The stopping guard still reacts to predicted/uncertain entry
immediately. Preserve the failed anchor probe; no validation seeds were opened.

## Amendment after the first fresh cohort

The v2 candidate passed72/72 development and16/16 native development, then
239/240 fresh Python runs. Combined/16/7069 had no collision but lost all useful
head paths after only a brief stable return; recovery and progress failed. Preserve
that entire fresh cohort and its frozen source as settling-v2. Native fresh seeds
were NOT opened because the Python gate failed. This is a validation failure, not
an ordinary pass or an invalid-run exclusion.

The revised candidate permits a bounded4 m/s head slowdown instead of2 m/s; the
60 m reserve threshold, causal received-beacon inputs, original TTLs and150 m range
remain. This is finite-scenario connectivity support, not a universal link-retention
proof. Development adds the exposed7069 failure, now explicitly development data.
Fresh Python seeds are replaced completely by the never-opened9001-series below.
Native8009-series seeds remain unopened and are still fresh. All prior failures
and sources are retained. Python worker count is4 on the four-core environment;
this changes orchestration only. New roots settling-v3 and settling-native-v2 are
required before any final confirmation.

## Established-following guard amendment before replacement validation

The4m/s-only probe passed combined/16/7069 but reproduced a path-loss failure on
combined/16/6121. The partially completed settling-v3 development grid was aborted
with21 completed records, its source snapshot and an explicit ABORTED marker; no
replacement validation seeds were opened. Retain the complete probe and partial
grid. Merely increasing head slowdown is insufficient.

Inspection found conservative adjacent-lane guarding could stop an ego that had
already positively admitted its in-lane predecessor. Initial approach must still
use the broad guard (the earlier always-narrow probe collided before admission).
After an OBSERVED cut-in, THREE DISTINCT fresh, unblocked selected-source stamps
now establish following. Only then may the same lane-aware predicted-intrusion
guard be used during ordinary following. Repeated ticks on one source stamp do
not count. A new selected target resets confirmation. Missing target knowledge
still requests full braking, and predicted intrusion remains a guard concern.
Positive exit still independently enables recovery. This phase uses observations,
not target names or fixture times. Six source-frozen probes, including both known
high-speed combined failures, passed before the new complete development grid.
Final roots are settling-v4 (96 development,240 entirely new validation) and
settling-native-v2 (16 development,80 unopened native validation). All earlier
source/evidence remains preserved. The gates below are unchanged.

## Frozen cohorts and gates

- All runs70 s, 20 Hz control. Python:8 profiles×speeds8/12/16×development seeds
  6101,6113,6121,7069 =96. Fresh seeds9001,9011,9013,9029,9041,9043,9049,9059,9067,9091
  give240. Native:all8 profiles (now also V2V-blackout and combined); development
  speed8,seeds6203/6211 =16; fresh speeds8/12,seeds8009,8011,8017,8039,8053 =80.
- Radio remains150 m in Python links, native Emitter configuration and runtime
  setRange. No300 m adapter is used. Native curved radius600 m, Python800 m.
  The physical road is extended to station1500 m for long-horizon validity.
- Original safety/freshness/requested-bound/lane gates remain. Require at least
  60% cruise-distance progress, correct fresh intruder samples, a continuous2 s
  correct head return after exit, and continuous2 s settling by60 s elapsed.
- During the final5 s:headway-error RMS≤2 m,max absolute≤5 m; relative-speed
  RMS≤0.5 m/s; correct fresh head association≥95%; leader cruise-speed RMS≤0.5 m/s.
  The last condition prevents passing by permanently slowing the whole formation.
- Correct radio-derived identity must agree with the physical head; geometry is
  checked independently. Original timestamps, source TTLs(.2 radar/.4 radio),
  replay/duplicate semantics and uncertainty are never refreshed by mode changes.
- Python validation opens only after Python development passes and source hashes
  match. Native validation additionally requires both development gates and Python
  validation. If a runtime change is needed after opening validation, use new
  development roots and new fresh seeds. Preserve all failures.

## Operating limits and proof scope

150 m is a direct-link model range, not an RF guarantee. Recovery requires an
actual fresh radar/radio path; pacing only improves the chance of retaining it.
Separate deliberately unreachable Python/native diagnostics must retain the failed
recovery classification and demonstrate braking with no invented target. They are
not included as ordinary recovery successes.

The new broader proof is **a posteriori continuous 2-D trajectory certification**,
not a prospective full-source controller-invariance theorem. Under endpoint-pose/
body bounds, coordinate acceleration≤20 m/s² and yaw rate≤2 rad/s, a separating-axis
bridge inequality proves disjoint footprints throughout each logged interval.
Fixed-point interval Taylor sin/cos and exact rational/integer comparisons avoid
optimistic floating collision thresholds. SMT checks the algebraic implications;
the continuous bridge/rotation lemmas are analytical. Native10 ms motion logging
qualifies measured refinement premises separately from commanded acceleration.
It does not establish unmeasured physical bounds or certify every future behavior.

Association is checked as a separate observation/identity property; the finite
physics certificate includes every actual actor and therefore does not rely on
an ego target label for collision scoring. This use of truth is post-control only.
Gaussian errors remain empirical inputs; no deterministic Gaussian-error guarantee,
hardware, real-time, comfort or string-stability claim is made.
