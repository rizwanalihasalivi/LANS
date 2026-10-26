# Independent revision12 verification

Verified: **True**. Independently selected gate: **none**. Complete 1080/1080 balanced development grid; all 1080 survived. Frozen source commit `c49ddc065caf9c93eb4867b91446a8037a11ffc7`.

No project module was imported, report12 was not invoked, no experiment ran, and no reserved split was opened. The audit script and outputs are confined to `/tmp`.

| Method | Mean penalized RMSE | Gain vs LQR | Survival |
|---|---:|---:|---:|
| lqr | 0.0842402149 | +0.000000% | 108/108 |
| legacy_fixed_m004 | 0.0835587586 | +0.808944% | 108/108 |
| legacy_fixed_p004 | 0.0839236141 | +0.375831% | 108/108 |
| legacy_student | 0.0825931813 | +1.955163% | 108/108 |
| preview_fixed_m004 | 0.0833161976 | +1.096884% | 108/108 |
| preview_fixed_p004 | 0.0836683820 | +0.678812% | 108/108 |
| preview_student | 0.0821142533 | +2.523690% | 108/108 |
| lateral_fixed_m004 | 0.0784576357 | +6.864393% | 108/108 |
| lateral_fixed_p004 | 0.0765555371 | +9.122339% | 108/108 |
| lateral_student | 0.0804260985 | +4.527667% | 108/108 |

| Region | Preview student gain vs LQR | Lateral student gain vs LQR | Lateral student gain vs legacy | Lateral student gains vs LQR, seeds 701 / 802 / 903 |
|---|---:|---:|---:|---|
| nominal | +4.205327% | +6.547124% | +3.241068% | +7.4935% / +6.0429% / +6.1076% |
| tire_mismatch | +1.772645% | +4.330726% | +3.048058% | +3.4959% / +4.0413% / +5.4471% |
| low_friction | +2.667221% | +4.536150% | +2.434033% | +4.5818% / +3.7573% / +5.2734% |
| sensor_stress | +3.331708% | +4.925778% | +2.548035% | +3.8929% / +5.5628% / +5.3230% |
| latency20 | +4.493818% | +7.196591% | +3.844190% | +6.8644% / +6.0268% / +8.7052% |
| latency100 | +0.000000% | +0.000000% | +0.000000% | +0.0000% / +0.0000% / +0.0000% |

Preview improves on legacy student by only 0.579864% (<1%), with zero qualifying >=1% stress-region gains; it passes learned benefit against both constants (1.442630% / 1.857486%). Gate progress fails.

Lateral passes gate progress but loses to both same-gate constants: student reductions against negative/positive constants are -2.508950% / -5.055887%. Its 4.527667% overall LQR gain is smaller than the constants' 6.864393% / 9.122339%; learned benefit fails.

Neither student reaches 5% in any of the three predeclared stress-region aggregate means. Lateral exceeds 5% in nominal and latency20, with improvement in all three paired means, but these regions are outside that target. The five-percent stress and overall targets fail.

All 21 archived source SHA-256 hashes match the manifest, the frozen git commit, and the current source; all 9 student/normalizer/completion artifact hashes match. All 60 archived trace episode metrics agree with raw CSV rows. Exact severe fallback holds for all 18 cells / 162 method-versus-LQR hash-and-score comparisons, and the stored severe observable trace fields match exactly.

The JSON contains full means, survival and gains by method, region, seed, and region × seed, individual provenance checks, and each frozen screen decision. Existing selection/report overall arithmetic and decisions agree.

Limits:

- Only 3 paired student/noise seeds, 3 speeds, 2 known paths and 6 known regions: descriptive development screening, not independent-domain or statistically established superiority.
- All 1080 episodes survived; failed-tail penalty algebra was checked, but no failed case exercises the penalty path in this run.
- 18 severe-delay cells have exact logged trajectory hashes across all 10 methods (162 candidate-versus-LQR comparisons); 10 stored severe traces also have exactly equal recorded observable trajectory/command fields.
- Only pair0/25m/s/dlc220 is traced (60 of 1080 episodes). Traces omit lateral velocity and yaw-rate state components used in the full trajectory digest, so a complete independent digest reconstruction from traces is impossible; this audit verifies hash equality and manifest provenance, not rerun physics.
- The completion manifest declares zero training steps and reserved_split_opened=false. This audit opens no reserved data and launches no experiments; filesystem/provenance checks cannot prove that no separate process ever accessed other data.
- Nominal and latency20 are not members of the frozen three-region stress target; passing 5% there cannot replace the predeclared stress requirement.
- The lateral fixed positive correction is a predeclared control, not a newly learned result or a post-test deployable selection. Gate-dependent closed-loop feature history differs despite frozen student weights.
- No native Webots/real-vehicle safety, formal stability, hard-real-time execution, unseen-road generalization, or SOTA comparison follows from this offline run.
