# Supplementary component study, frozen before execution

64 development cases: four traffic scenarios x four traffic replicates x four
profiles (nominal, 100 ms command FIFO, traffic blackout followed by unexpected
NPC braking, ego blackout). Each requests 12 seconds. A separate fixed namespace
generates off-grid stiffness, initial perturbations, speed and traffic geometry.
The traffic-braking disturbance starts at 2 s; blackout starts at 1 s. Its hidden
future is never provided to control. All 384 planned episodes are retained.

Six paired variants: full hybrid, without PPO, without adaptation, without
application-time prediction, without traffic expiry and without interaction
supervision. The last three are deliberately incomplete simulated component
ablations, not deployable controllers. The no-expiry variant retains original
timestamps and age-dependent spatial uncertainty. The no-interaction variant
removes both traffic-based candidate screening and longitudinal intervention;
it does not isolate braking alone. All other physical/proposal limits remain.

Use seed 42's original frozen policy for functional component comparisons;
multi-actor training variability is covered separately by the formal campaign.
This study cannot establish cross-actor component effects. Log every tick and
replay the plant and physical FIFO independently of controller forecasts.
Failure-penalized RMSE charges all missing ticks after early termination.

Primary outcomes: collision/corridor/early-termination counts and penalized RMSE.
Also report progress, heading/rate, minimum clearance, braking/backup counts and
warning precision/recall versus a disclosed current-truth geometric CV proxy.
Task completion means reaching x=60 m within the requested 12 seconds; record
first passage time separately. Completing the requested duration does not imply
reaching the distance goal. Record acceleration jerk descriptively, without an
invented jerk limit or comfort pass claim.
Proxy labels are not future actual-collision labels. Bootstrap paired differences
over the 16 scenario/traffic fixtures, holding all four profiles together.
Use 5,000 draws, seed 24310001, and report all five contrasts with Holm correction
for paired exact fixture-level sign tests of failure-rate differences (five-test
family). RMSE and other intervals are descriptive secondary outcomes. No
significance-driven case selection.
Incomplete safety variants may fail; those outcomes are expected to remain.

This is an additional declared development experiment, not an opened reserved
cohort, a replacement promotion criterion, or a Webots/native validation result.

A secondary controlled prediction/ranking diagnostic samples every 20th tick
with a fresh ego measurement in full-controller episodes. Compare nominal and
causally estimated plant predictions on the same fixed 13-command residual grid.
Use hidden stiffness and current-truth CV traffic only in scoring. Report cost
MAE, Spearman rank agreement, true-grid regret and application-position error.
These labels hold future feedback/acceleration and traffic assumptions fixed;
they are not realized closed-loop full-plan counterfactual outcomes. Report
position error separately on delayed-command cases to avoid dilution by the
zero-delay cases' identically zero application-state forecast interval.
