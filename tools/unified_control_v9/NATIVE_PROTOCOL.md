# Fixed native physical transfer check

After complete frozen Python evaluation and zero hybrid safety failures, run
exactly 16 native Webots R2025a cases: straight/sine routes, 8/16 m/s, and LQR
plus every new PPO hybrid endpoint (42, 43, 44). Each lasts six seconds after
ten seconds of actual physical acceleration/settling. Phase 9, amplitude 1.15,
initial lateral error 0.3 m and heading offset 0.005 rad are fixed in advance.
A separate 10 m/s, phase 0.5, half-second LQR/hybrid-42 technical smoke checks
the interface before freezing the final source. No endpoint or case selection.

The native articulated body, wheel joints, tire contacts, and cruise motor
controller integrate ego motion. The bridge never calls Python `advance` or
`Pipeline.apply` for ego and never overwrites pose or velocity. After warmup a
fixed map transform expresses the measured vehicle relative to the route; it
does not move the car. Current ideal position, orientation, body velocity and
yaw-rate samples enter the same timestamped packet/controller interface.
Native left/right steering sensors are recorded separately from requested input.

Use the same 50 ms controller period, command FIFO, 0.5 rad steering bound,
0.6 rad/s command rate, selected v9 controller and all three frozen policies.
The bridge ramps the physical steering setpoint at 0.6 rad/s in 1 ms physics
steps and records the maximum measured wheel rate. This finite actuator slew
differs from the Python zero-order-held plant. The cruise target is current
measured forward speed plus requested acceleration times 50 ms, clipped to
zero/target speed. Requested acceleration is not an exactly imposed native
body force; actual speed is logged. Prediction still uses the analytical model,
with uncertainty guard preserved, so dynamics mismatch is an outcome.

The existing pinned chassis/prototypes and development tire-contact calibration
remain fixed. Calibration used open-loop 15..25 m/s cases: the 8 m/s condition
is an explicit extrapolation, not a newly calibrated match. Full native state,
sensor steering, actuator requests, controller decisions, timestamps, source
hashes and policy hashes are saved as raw JSON. Whole-run RMSE uses the same
2.5 m squared penalty for uncompleted ticks, and corridor errors over 1.75 m
remain failures. Heading/rate/progress and every failure remain reported.

PPO and conic planning run in actual spawned workers. Each simulation tick is
paced toward 50 ms of wall time to permit causal replies. No blocking solver
wait is introduced inside the controller; startup/close are excluded. Record
input-to-decision and full native-cycle wall times and all misses, including
simulator scheduling delay. These measurements are engineering observations,
not a formal worst-case execution-time guarantee. Preserve stale-action guards.

This world contains one vehicle and no interacting traffic. Collision avoidance,
V2V loss, intersection arbitration and complete framework transfer are therefore
not validated here. Native progress and secondary-metric regressions cannot be
hidden by tracking RMSE. Native outcomes are not used to tune this frozen cohort.
