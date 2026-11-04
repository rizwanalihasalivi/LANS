# Native actuator refinement after an exposed fresh failure

The common Python controller, scenarios, gate definitions and exact 2-D primitive
remain frozen at settling-v4:96/96 development and240/240 fresh Python pass.
No Python validation input is used to retune those files.

The first new native campaign passed16/16 development, then exposed a collision
in noisy_nonconnected/8/8011. It was aborted with42 completed fresh records,
41 passes and one failure; unfinished raw runs and the exact36-file source remain
in settling-native-v2. All8009,8011,8017,8039,8053 validation seeds are now opened,
including profiles not reached before cancellation. They cannot be fresh again.

The controller requested-6 m/s², but actual native deceleration was about2.8 m/s².
The inspected pinned Webots Driver source shows SPEED mode sets wheel-motor
velocity; it does not apply the separate friction-brake intensity automatically.
An acceleration command must not be confused with its physical realization.

An explicit-brake-in-SPEED-mode probe also failed the exposed case. Car.proto's
time0To100=10s sets a2.7778m/s² velocity-motor ramp, enforced by large motor torque;
friction braking cannot override that velocity servo consistently. Preserve that
failed probe, including the collision before its subsequent heading violation.

A TORQUE-mode friction-brake probe resolved the exposed8m/s collision but failed
three other recovery/pose cases. Retain that complete probe and its source; it is
not accepted. The final candidate keeps the original stable SPEED-mode plant.

A native-only observation guard plans with2.5m/s² braking and0.8s reaction reserve,
using the common controller's fresh guard objects and lane-relevance decision.
Its stopping demand is2+0.8v+max(0,v²-v_object²)/(2*2.5). It can replace the nominal
acceleration by maximum braking before the common6m/s²-based guard would trigger.
Raw common controller commands and the native override are logged separately and
replayed exactly. No simulator truth, case/seed, target script or new sensor enters.

A further probe with earlier planning and corrected Radar aperture passed three
regressions but failed combined12/8011 heading qualification. Mixing locked
friction brakes with the strong velocity servo was not accepted. The candidate
keeps friction intensity0 and uses the stable factory SPEED-mode motor braking.
Maximum requests set cruise target0; a six-tick
0.3s release hold bridges intermittent observations. Leaving this mode clears the
brake and anchors the cruise integrator to measured speed. World friction, mass,
brake coefficient and the original time0To100 field do not change. Actual braking
remains measured; no equality with the requested-6 is asserted.
The first earlier-braking probe removed collisions but exposed repeated false
adjacent-vehicle braking during overtaking. Pinned R2025a WbRadar.cpp explicitly
clips target-center azimuth to the physical+/-0.35rad edge if only part of a body
is inside the frustum. Treating that clipped bearing as a center pulled an actual
3.5m adjacent target toward the lane. The native adapter now uses the same0.33rad
central aperture as the Python model and rejects the ambiguous outer fringe.
Raw returns remain archived; rejection is unavailable evidence, not a complete
clear-road scan. Selected-target loss still brakes. No physical FOV is enlarged.
The inspected official source and its SHA are retained in the sensor-refinement
evidence root. Gaussian errors remain unbounded; visibility is an explicit limit.
Ordinary negative requests remove positive setpoint windup. The actual API brake
and cruise settings are read back and logged. Steering, requested acceleration
bounds, source TTLs,150 m links, head pacing, target logic and the Python model do
not change. Actual acceleration/yaw and body-pose qualification remain mandatory;
there is no claim that measured acceleration equals the requested command.

Before fresh native confirmation, use a NEW native root settling-native-v3,
full development speeds8/12, seeds6203 and8011, all8 profiles:32 development runs.
The exposed8011 is explicitly development data. Probe the known8 m/s failure,
the older150 m seed2003, a12 m/s curve and combined12 m/s before that full grid.
Retain all probes and any failure. New native fresh seeds12007,12011,12037,12041,
12043 with speeds8/12 and all8 profiles give80 previously unopened trials.

Open these fresh inputs only after the32 development runs, independent audit,
native actuator replay, all-actor continuous certificates, the semantic negative
controls and the complete V2V test suite pass. The original35 s/2003 exposed
failure is a separate regression, excluded from fresh denominators. All ordinary
70 s metrics and strict collision/association/spacing gates remain unchanged.
No failed native run is relabelled invalid or excluded as a recovery success.

The broader proof remains conditional a posteriori continuous finite-trace
certification. Sampled native qualification does not prove every unmeasured
derivative or prospective safety of all future actions. Final benchmarking stays
on hold, and no hardware safety claim is introduced.
