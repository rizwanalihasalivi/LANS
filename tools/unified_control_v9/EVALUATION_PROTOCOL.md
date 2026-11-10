# Prospective comparison and independent final validation

Freeze the calibrated asynchronous controller, both geometric calibrations and
all three new continuation endpoints before evaluation. Retain all three old
endpoints too. No candidate, seed, checkpoint or case selection follows these
outcomes. Development and final data use independent declared RNG namespaces;
none is used for training or calibration. This final set is new and leaves all
older reserved cohorts unopened.

Development: 32 balanced scenario/mirror/speed/stiffness cells, seed 11913000,
route phase 20, amplitude 1.25, independently randomized offsets/heading and
initial traffic positions/speeds. Final: 64 cells, seed 12913000, four scenarios
times two speed strata times two communication strata times four independent
replicates. Randomize mirror, continuous speed/stiffness, offsets/heading, road
phase/amplitude, traffic positions/speeds and communication realization. Keep
all outcomes. Scenario/speed/communication strata define the bootstrap clusters;
actor and within-stratum cases are averaged, never treated as independent seeds.
Confidence intervals characterize this finite test distribution, not all roads.

Every development/final case uses LQR, fixed correction, deterministic correction,
nominal optimized, adaptive-only, frozen v8 synchronous optimized and adaptive-only,
Stanley adaptation, pure-pursuit adaptation,
new PPO-only (three actors), asynchronous hybrid with frozen original PPO
(three actors), asynchronous hybrid with new PPO (three actors), and v8
synchronous hybrid with original PPO (three actors): 21 records per case.
Retain original 160 development and 120 stress regression records plus 120 new
stress records. Total 2,416 logical-time evaluation episodes (672 development,
1,344 final, 400 regression/stress). The frozen v8 optimized/adaptive references
were added during pre-outcome review to retain the strongest prior analytical
references; the new strict asynchronous versions remain separate comparisons.
All receive the same physical plant,
initial traffic, packet realization, supervisor, actuator limits and whole-run
failure-penalized six-second score. Controller computation architecture and
declared model adaptation differ explicitly; wall time is evaluated separately.

Primary outcomes: per-reference mean whole-run RMSE gain and clustered bootstrap
95% intervals (5,000 draws, seed 13913000), each-actor gains, failure/collision,
mean heading and rate ratios and every-cell progress. Keep original 5% LQR/1%
optimized positive-confidence, <=10% quality and >=99% progress rules. Additional
goals: no heading/rate increase, substantial learned benefit over adaptive-only
and frozen-PPO hybrid, zero observed 50 ms misses, and the still-requested 30%
gain against every implemented reference. Report each separately, including
tiny effects and failures. Geometric-law comparisons are adaptations, not full
paper reproductions or a completed state-of-the-art/novelty evaluation.
The 30% observed-mean goal and the stronger per-comparison lower-confidence-bound
goal are separate flags. Bootstrap intervals are per comparison and have no
family-wise multiplicity adjustment; neither flag establishes a universal gain.

Final evaluation runs once after all choices freeze, irrespective of desired
performance. It is validation, not permission to tune. Python safety must pass
before native physical transfer is attempted; native outcomes cannot be inferred
from analytical traces. No thesis draft, figures or presentation tables.
