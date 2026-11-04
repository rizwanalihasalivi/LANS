# Predeclared conditional-safety experiment protocol

Date: 4 November 2026 (Asia/Shanghai). Parent checkpoint: `9daa1487`.
This is a new reference longitudinal safety study. Earlier evidence stays frozen;
final thesis benchmarking/comparisons remain on hold.

The claim and assumptions are fixed in THEOREM.md before fresh validation. Nominal
following reuses LANS damped position/velocity gains and 1.2 s headway; the shield
accepts arbitrary proposals. This is an adapter-level 1-D reference experiment,
not an unchanged execution of RobustFollower or the Webots bicycle plant.

- Exact rational non-reversing flow; h=0.05 s; episode=40 s; m=2 m; b=5.5 m/s²;
  command uncertainty bound δ=0.25 m/s²; emergency u=−5.75 m/s²; maximum u=2.5.
- Ego position/speed sensing bounds 0.05 m / 0.05 m/s. Radar rear-position error
  bound 0.15 m; radio rear-position error bound 0.10 m. Truth errors are sampled
  WITHIN bounds, not Gaussian-clipped data presented as Gaussian assurance.
- Messages keep original timestamps, with independent sequence/replay checks;
  radar TTL 0.2 s, V2V TTL 0.4 s. Lower-bound memory is retained independently of
  fresh nominal state. One/two-tick latency, 10% loss, duplicates/out-of-order and
  rejected old records are exercised. Initial valid protected observation is an
  explicit initialization premise.
- Eight profiles: steady_connected, leader_emergency, v2v_blackout, dual_blackout,
  bounded_sensor_error, admissible_cutin, adversarial_nominal, permanent_blackout.
- Speeds 8/12/16 m/s. Development seeds 4001,4003,4007 (72 runs). Fresh seeds
  5003,5009,5011,5021,5023,5039,5051,5059,5077,5081 (240 runs).
- Fresh validation may start ONLY after all development, independent replay,
  theorem checks and boundary checks pass and source hashes match the freeze.
  Any runtime/scenario/scoring change requires new output roots and new validation
  seeds if the former validation cohort has been opened. Preserve failures.
- Every run must satisfy the exact invariant/guard, input-bound containment,
  update timing and actuator-envelope conditions and continuous within-tick bumper
  gap ≥2 m for every admitted object. No tolerance can hide a negative margin.
  No positive progress gate is imposed: permanent blackout may require stopping.
  Progress, stopped time and spacing are reported separately, without convergence
  or superiority claims. Sampling is supporting evidence, not the theorem.
- Deterministic boundary grid varies b, h, speed, available slack and nominal
  command, including equality and zero-speed stop branches. Verify every emitted
  guard independently. Negative controls must detect unsafe initialization,
  unguarded acceleration and breached model assumptions. A deliberately unsafe
  cut-in is OUTSIDE the theorem and may collide; retain its result.
- Source freezes, proof obligations/logs, every final raw trajectory, independent
  audit, negative checks, report and archive-member SHA-256 hashes are published.
- Existing curved/dense Gaussian/noisy Webots evidence is contextual empirical
  evidence. It is NOT a validation cohort of the new longitudinal theorem.
