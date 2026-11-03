# Explicit native communication operating envelope

Prepared before 300 m outcomes. The original 150 m fresh validation remains
preserved, including recovery failures. It must not be relabeled as passing.
Safety/freshness/requested-bound gates remain unchanged. The follower/control law,
tracking gates, noise, misses, physics, routes and maneuver schedules are unchanged.

A non-connected intervening car cannot relay a head vehicle's state. Once the
head is outside all available radio paths and radar range, a stopped follower
cannot recover the head's state from absence. The 150 m native case exposed this
coverage limit. Assess a separate 300 m Emitter operating envelope, supported by
the simulator, with the existing 300 m selector relevance bound and original TTLs.
This is a configuration sensitivity result, not proof of a stronger controller
under the same 150 m conditions or a real RF link-budget/range validation.

Only generated world Emitter ranges and the generated controller's `setRange`
literal change from 150 to 300. Assert the inverse replacement reproduces original
bytes. Hash/archive the ACTUAL generated world and controller. No underlying
template or previous experiment is edited. All message types use this explicit
radio range; local radar remains 120 m. Native common source stays frozen.

Development: six profiles, cruise 8 m/s, seeds 811/821 (12 trials). Fresh validation:
the same six profiles, cruise 8/12 m/s, NEW seeds 3001/3011/3019 (36 trials), after
all development gates pass. These seeds have not guided changes. Python's frozen
240-trial 150 m validation remains reported with its own assumptions. Retain all
150 m native validation trials as a complete diagnostic cohort, not just failures.

Required native checks, 35 s / 700 control samples per car: original independent
scoring, source/world/controller hashes, all-pair sampled box overlaps, pose/road
envelopes, original-age input replay, bounded forwarding, cooperative source
consistency, progress and target acquisition/return. Also report spacing, stopped
time and return censoring. No threshold may change to turn a failed trial green.

The configured workflow can claim readiness only in its declared tested operating
envelope. Arbitrary coverage, hidden-object observability, real-world safety and
final thesis benchmarking remain outside this result.
