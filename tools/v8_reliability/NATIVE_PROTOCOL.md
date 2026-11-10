# Native reliability protocol, before native outcomes

Use actual R2025a rigid-body/tire dynamics; never integrate the Python ego plant
for native scores. Keep the shared R16 steering baseline, physical angle and
acceleration bounds and proposal TTLs. Native actuator setpoint slew is tightened
from0.60 to0.59rad/s for ALL matched roles to reserve margin for measured servo
overshoot; actual steering rate must still be measured and reported. This change
is explicit and does not establish a physical rate guarantee.

Use unchanged original policy endpoints42/43/44. Original-v8 and selected
new execution receive the same ego sensing, vehicle, route, timing schedule,
actuator interface and actor weights. Fixed-release wait uses a short yielding
spin and never rebases/drops a release after an overrun. Reversible affinity
applies only to the owned controller and its worker processes; log whether it
succeeds. Report startup/JIT separately, and preserve all deadline misses.

Timing includes sensor acquisition, worker handling, controller decision,
50 actual Webots physics substeps, inline JSON trace serialization/write/flush.
An immutable timing sidecar captures the complete end of each cycle; writing
that sidecar occurs after the episode. Response, local complete-cycle and
scheduled complete-cycle misses remain distinct metrics. Do not use pre-log
cycle timestamps as the complete-cycle result.

Native confirmation follows passing current Python safety checks and controller
freeze. The first engineering smoke is development data. Formal comparisons
use straight/sine roads at8/16m/s and all three actors; LQR and the old/current
hybrids get matched cases. No favorable-case or actor selection. Single-vehicle
transfer cannot establish V2V traffic or collision avoidance; that boundary is
retained, and the emergency traffic recourse requires a separate native traffic
cohort before any native claim. No PPO retraining, new drafts, figures or tables.

Revision2 addendum before formal native outcomes: use the analytical V2 traffic
supervisor after its54 exposed regressions and1240-record prospective safety
confirmation. The earlier two engineering smokes used V1. This single-car world
does not exercise the new traffic mechanism; its scope remains actuator/plant/
tracking/timing transfer of the selected wrapper with the unchanged actors.
