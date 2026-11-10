# Geometric steering-law adaptations

Stanley uses a front-axle signed cross-track error and heading correction,
delta = heading_error + atan(k * cross_track_error / speed). Bibliographic
origin: Thrun et al., “Stanley: The robot that won the DARPA Grand Challenge,”
Journal of Field Robotics 23(9), 2006, DOI 10.1002/rob.20147. The code checks
the steering-law implementation against the saved PythonRobotics Stanley
implementation, not an independently inspected full primary-paper reproduction.

Pure pursuit uses rear-axle geometry and circle curvature
kappa = 2 * target_lateral_offset / target_distance_squared, with
delta = atan(wheelbase * kappa). Bibliographic origin: R. Craig Coulter,
“Implementation of the Pure Pursuit Path Tracking Algorithm,” CMU-RI-TR-92-01,
1992. Primary full-text inspection remains outstanding; the saved PythonRobotics
implementation is the implementation reference.

Implementation references, fetched from AtsushiSakai/PythonRobotics master:
`PathTracking/stanley_controller/stanley_controller.py` and
`PathTracking/pure_pursuit/pure_pursuit.py`. The fetched text is preserved under
`references/` and never executed as a dependency. SHA256 respectively:
`ec426a511821620d798a46a35f0ab64382bd79ff417e0f59fb0c1f7873d8c7a0` and
`d6702311927cb44cbe27546e6e76ba0b7371a6b0715013ac2a40735b299779eb`.

Declared adaptations: continuous analytic-road projection rather than waypoint
search; physical axle positions from the common vehicle; steering/slew limits;
the shared packet reconstruction, command FIFO, traffic expiry and longitudinal
supervisor; and a robust prediction of each geometric law's own steering tail.
They receive no true stiffness or future NPC trajectory. Stanley tests gains
0.5/1/2; pure pursuit tests lookahead 2+T*speed with T=0.1/0.3/0.5. All parameters
are calibrated on the same 64 training fixtures before prospective evaluation.
Failed candidates and any diagnostic fallback are retained explicitly.

These are standard controller-family adaptations. They do not close the closest
delay-aware MPC/predictive-safety-filter reproduction gap, establish a new
algorithmic novelty claim, or justify a state-of-the-art label. Existing reviewed
papers in `docs/research/primary-papers/` describe important overlap; stronger
novelty and closest-method claims remain unsupported without further evidence.
