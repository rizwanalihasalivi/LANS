# V2 analytical traffic-supervision repair, before V2 outcomes

V1's2309 records, its failed original performance gate and its exposed final
case42 progress failure remain unchanged. They are no longer held-out data for
V2. No PPO/actor/reward/feature changes, and no tuning on any new final outcome.

V1's actual-circle contact test used a fixed uncertainty radius for future TTC,
although command admission grows that radius by0.6m/s. Its ray-intersection
test also discarded a vehicle as soon as its center passed the crossing, even
while its expanded occupancy interval still included future time. V2 uses the
same current-age radius and unchanged0.6m/s growth in both contact predictors,
and tests future interval overlap including a passed center's remaining tail.
Missing-source/ego expiry and force-stop braking, physical limits, recourse
labels, original v8 reference and selected1.10/1.075 settings remain unchanged.

First run the5 exposed training crossing cases plus the exposed V1 final42 case
as development regressions, with matched LQR/optimized/adaptive/current3 actors
and original-v8's3 actors. All54 records and failures are retained. A successful
repair requires zero current failures, >=99% matched LQR progress for each
current actor, and no missing-source or physical-limit regression. If these fail,
do not replace the V1 candidate or open a V2 prospective confirmation. This is
a supervision development repair; none of its safety benefits belongs to PPO.
