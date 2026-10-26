# Revision13 development results

Executable freeze: `583ee07e1ec8f8ce61eb457796e301f8dd9750ac`. Verified 5616 complete-grid episode records, archived source hashes, metric arithmetic, physical bounds and severe-delay fallback. Additional training steps: 0.

Each method has 432 paired cells. Mirrored orientations share transformed noise and initial errors; they are correlated symmetry checks, not additional independent seeds. Means give equal weight to episodes.

## Overall metrics

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 432/432 | 0.06907929 | 0.01500902 | 0.06089837 | 0.50561434 | +0.000% |
| lateral_fixed_m004 | 432/432 | 0.06423193 | 0.01514382 | 0.08346900 | 0.75542663 | +7.017% |
| lateral_fixed_p004 | 432/432 | 0.06423193 | 0.01514382 | 0.08346900 | 0.75542663 | +7.017% |
| lateral_student | 432/432 | 0.06623960 | 0.01489392 | 0.12361385 | 1.23325575 | +4.111% |
| balanced_light_fixed_m004 | 432/432 | 0.07004306 | 0.01520162 | 0.06131432 | 0.51135671 | -1.395% |
| balanced_light_fixed_p004 | 432/432 | 0.07004306 | 0.01520162 | 0.06131432 | 0.51135671 | -1.395% |
| balanced_light_student | 432/432 | 0.06912163 | 0.01501684 | 0.06101548 | 0.50703026 | -0.061% |
| balanced_medium_fixed_m004 | 432/432 | 0.07219097 | 0.01544129 | 0.06126144 | 0.50965264 | -4.504% |
| balanced_medium_fixed_p004 | 432/432 | 0.07219097 | 0.01544129 | 0.06126144 | 0.50965264 | -4.504% |
| balanced_medium_student | 432/432 | 0.06911823 | 0.01501497 | 0.06097395 | 0.50642876 | -0.056% |
| balanced_strong_fixed_m004 | 432/432 | 0.07560223 | 0.01561819 | 0.06061946 | 0.50542987 | -9.443% |
| balanced_strong_fixed_p004 | 432/432 | 0.07560223 | 0.01561819 | 0.06061946 | 0.50542987 | -9.443% |
| balanced_strong_student | 432/432 | 0.06908902 | 0.01501783 | 0.06103745 | 0.50676443 | -0.014% |

## Frozen candidate checks

| Candidate | Pass | Failed checks |
|---|---|---|
| balanced_light_fixed_m004 | False | overall_lateral_gain, retain_lateral_gain, all_three_pair_means_better, each_geometry_orientation_better, nominal_tracking_preserved, active_region_tracking_preserved |
| balanced_light_fixed_p004 | False | overall_lateral_gain, retain_lateral_gain, all_three_pair_means_better, each_geometry_orientation_better, nominal_tracking_preserved, active_region_tracking_preserved |
| balanced_medium_fixed_m004 | False | overall_lateral_gain, retain_lateral_gain, all_three_pair_means_better, each_geometry_orientation_better, nominal_tracking_preserved, active_region_tracking_preserved, overall_heading_preserved |
| balanced_medium_fixed_p004 | False | overall_lateral_gain, retain_lateral_gain, all_three_pair_means_better, each_geometry_orientation_better, nominal_tracking_preserved, active_region_tracking_preserved, overall_heading_preserved |
| balanced_strong_fixed_m004 | False | overall_lateral_gain, retain_lateral_gain, all_three_pair_means_better, each_geometry_orientation_better, nominal_tracking_preserved, active_region_tracking_preserved, overall_heading_preserved, active_region_heading_preserved |
| balanced_strong_fixed_p004 | False | overall_lateral_gain, retain_lateral_gain, all_three_pair_means_better, each_geometry_orientation_better, nominal_tracking_preserved, active_region_tracking_preserved, overall_heading_preserved, active_region_heading_preserved |

Selected candidate: **none**.
Next action: `stop_reserved_native_and_learning`.

## Region: nominal

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05357885 | 0.01325398 | 0.05936281 | 0.48198487 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.05007771 | 0.01327080 | 0.08927886 | 0.80718235 | +6.535% |
| lateral_fixed_p004 | 72/72 | 0.05007771 | 0.01327080 | 0.08927886 | 0.80718235 | +6.535% |
| lateral_student | 72/72 | 0.05058786 | 0.01303368 | 0.14181269 | 1.44467639 | +5.582% |
| balanced_light_fixed_m004 | 72/72 | 0.05458704 | 0.01346664 | 0.05964708 | 0.48687810 | -1.882% |
| balanced_light_fixed_p004 | 72/72 | 0.05458704 | 0.01346664 | 0.05964708 | 0.48687810 | -1.882% |
| balanced_light_student | 72/72 | 0.05357934 | 0.01325523 | 0.05939690 | 0.48230951 | -0.001% |
| balanced_medium_fixed_m004 | 72/72 | 0.05722035 | 0.01375723 | 0.05958410 | 0.48522916 | -6.797% |
| balanced_medium_fixed_p004 | 72/72 | 0.05722035 | 0.01375723 | 0.05958410 | 0.48522916 | -6.797% |
| balanced_medium_student | 72/72 | 0.05358285 | 0.01325491 | 0.05937489 | 0.48205441 | -0.007% |
| balanced_strong_fixed_m004 | 72/72 | 0.06045735 | 0.01390694 | 0.05879570 | 0.48023596 | -12.838% |
| balanced_strong_fixed_p004 | 72/72 | 0.06045735 | 0.01390694 | 0.05879570 | 0.48023596 | -12.838% |
| balanced_strong_student | 72/72 | 0.05358286 | 0.01325487 | 0.05937378 | 0.48203986 | -0.007% |

## Region: tire_mismatch

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.13665855 | 0.02229113 | 0.06413166 | 0.54514445 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.12167656 | 0.02264080 | 0.08980414 | 0.83221343 | +10.963% |
| lateral_fixed_p004 | 72/72 | 0.12167656 | 0.02264080 | 0.08980414 | 0.83221343 | +10.963% |
| lateral_student | 72/72 | 0.13018887 | 0.02182043 | 0.12483697 | 1.22796569 | +4.734% |
| balanced_light_fixed_m004 | 72/72 | 0.13825334 | 0.02253705 | 0.06507130 | 0.55627251 | -1.167% |
| balanced_light_fixed_p004 | 72/72 | 0.13825334 | 0.02253705 | 0.06507130 | 0.55627251 | -1.167% |
| balanced_light_student | 72/72 | 0.13687884 | 0.02232327 | 0.06457223 | 0.55030499 | -0.161% |
| balanced_medium_fixed_m004 | 72/72 | 0.14145532 | 0.02285259 | 0.06569995 | 0.56175838 | -3.510% |
| balanced_medium_fixed_p004 | 72/72 | 0.14145532 | 0.02285259 | 0.06569995 | 0.56175838 | -3.510% |
| balanced_medium_student | 72/72 | 0.13685169 | 0.02231857 | 0.06447613 | 0.54937734 | -0.141% |
| balanced_strong_fixed_m004 | 72/72 | 0.14912653 | 0.02327424 | 0.06501319 | 0.55634104 | -9.123% |
| balanced_strong_fixed_p004 | 72/72 | 0.14912653 | 0.02327424 | 0.06501319 | 0.55634104 | -9.123% |
| balanced_strong_student | 72/72 | 0.13672464 | 0.02233018 | 0.06474184 | 0.55082355 | -0.048% |

## Region: low_friction

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.06424971 | 0.01476514 | 0.06020205 | 0.49399954 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.05893762 | 0.01487811 | 0.08925389 | 0.81111521 | +8.268% |
| lateral_fixed_p004 | 72/72 | 0.05893762 | 0.01487811 | 0.08925389 | 0.81111521 | +8.268% |
| lateral_student | 72/72 | 0.06151938 | 0.01456299 | 0.13594748 | 1.37470387 | +4.250% |
| balanced_light_fixed_m004 | 72/72 | 0.06546091 | 0.01500983 | 0.06089496 | 0.50249870 | -1.885% |
| balanced_light_fixed_p004 | 72/72 | 0.06546091 | 0.01500983 | 0.06089496 | 0.50249870 | -1.885% |
| balanced_light_student | 72/72 | 0.06426754 | 0.01477019 | 0.06028336 | 0.49480895 | -0.028% |
| balanced_medium_fixed_m004 | 72/72 | 0.06845389 | 0.01536459 | 0.06078102 | 0.50006421 | -6.543% |
| balanced_medium_fixed_p004 | 72/72 | 0.06845389 | 0.01536459 | 0.06078102 | 0.50006421 | -6.543% |
| balanced_medium_student | 72/72 | 0.06427220 | 0.01476918 | 0.06025390 | 0.49426247 | -0.035% |
| balanced_strong_fixed_m004 | 72/72 | 0.07195883 | 0.01557146 | 0.06018336 | 0.49756919 | -11.999% |
| balanced_strong_fixed_p004 | 72/72 | 0.07195883 | 0.01557146 | 0.06018336 | 0.49756919 | -11.999% |
| balanced_strong_student | 72/72 | 0.06427331 | 0.01476946 | 0.06025493 | 0.49430614 | -0.037% |

## Region: sensor_stress

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05269728 | 0.01319875 | 0.06315015 | 0.55213001 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.05044819 | 0.01355096 | 0.09680964 | 0.90887640 | +4.268% |
| lateral_fixed_p004 | 72/72 | 0.05044819 | 0.01355096 | 0.09680964 | 0.90887640 | +4.268% |
| lateral_student | 72/72 | 0.05071593 | 0.01359766 | 0.15611263 | 1.63579101 | +3.760% |
| balanced_light_fixed_m004 | 72/72 | 0.05373683 | 0.01345396 | 0.06348771 | 0.55706275 | -1.973% |
| balanced_light_fixed_p004 | 72/72 | 0.05373683 | 0.01345396 | 0.06348771 | 0.55706275 | -1.973% |
| balanced_light_student | 72/72 | 0.05271337 | 0.01320389 | 0.06325240 | 0.55352589 | -0.031% |
| balanced_medium_fixed_m004 | 72/72 | 0.05600140 | 0.01372905 | 0.06297522 | 0.55001503 | -6.270% |
| balanced_medium_fixed_p004 | 72/72 | 0.05600140 | 0.01372905 | 0.06297522 | 0.55001503 | -6.270% |
| balanced_medium_student | 72/72 | 0.05270714 | 0.01320116 | 0.06318180 | 0.55237702 | -0.019% |
| balanced_strong_fixed_m004 | 72/72 | 0.05910429 | 0.01386751 | 0.06182777 | 0.54035225 | -12.158% |
| balanced_strong_fixed_p004 | 72/72 | 0.05910429 | 0.01386751 | 0.06182777 | 0.54035225 | -12.158% |
| balanced_strong_student | 72/72 | 0.05270661 | 0.01320101 | 0.06318223 | 0.55238114 | -0.018% |

## Region: latency20

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05379227 | 0.01327039 | 0.05907439 | 0.47968347 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.05075239 | 0.01324754 | 0.07619832 | 0.69242876 | +5.651% |
| lateral_fixed_p004 | 72/72 | 0.05075239 | 0.01324754 | 0.07619832 | 0.69242876 | +5.651% |
| lateral_student | 72/72 | 0.05092643 | 0.01307404 | 0.12350417 | 1.23565389 | +5.328% |
| balanced_light_fixed_m004 | 72/72 | 0.05472113 | 0.01346750 | 0.05931570 | 0.48468456 | -1.727% |
| balanced_light_fixed_p004 | 72/72 | 0.05472113 | 0.01346750 | 0.05931570 | 0.48468456 | -1.727% |
| balanced_light_student | 72/72 | 0.05379156 | 0.01327376 | 0.05911885 | 0.48048858 | +0.001% |
| balanced_medium_fixed_m004 | 72/72 | 0.05651574 | 0.01366956 | 0.05905920 | 0.48010539 | -5.063% |
| balanced_medium_fixed_p004 | 72/72 | 0.05651574 | 0.01366956 | 0.05905920 | 0.48010539 | -5.063% |
| balanced_medium_student | 72/72 | 0.05379636 | 0.01327127 | 0.05908785 | 0.47975764 | -0.008% |
| balanced_strong_fixed_m004 | 72/72 | 0.05946727 | 0.01381429 | 0.05842761 | 0.47733714 | -10.550% |
| balanced_strong_fixed_p004 | 72/72 | 0.05946727 | 0.01381429 | 0.05842761 | 0.47733714 | -10.550% |
| balanced_strong_student | 72/72 | 0.05374757 | 0.01327672 | 0.05920277 | 0.48029222 | +0.083% |

## Region: latency100

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| lateral_fixed_p004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| lateral_student | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_light_fixed_m004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_light_fixed_p004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_light_student | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_medium_fixed_m004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_medium_fixed_p004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_medium_student | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_strong_fixed_m004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_strong_fixed_p004 | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |
| balanced_strong_student | 72/72 | 0.05349912 | 0.01327472 | 0.05946914 | 0.48074366 | +0.000% |

## Interpretation limits

Heading and lateral tables use declared failure penalties; command, actuator-rate, total-variation and yaw metrics describe executed steps. Failed cases remain in denominators and survival is a separate required check. Full metric sums are stored for every episode; representative traces do not constitute complete telemetry for every case.
Fixed-sign reflection integrity passed 1944 paired comparisons at 1e-9 numerical tolerance. Opposite fixed signs should tie globally on the balanced mirror grid; that tie is not evidence of learning. The student need not be reflection-equivariant.
Frozen students retain their original weights and normalization. Student rows are comparators; this stage selects only a nonlearned balanced controller. Engineering heading/smoothness budgets are not certified comfort or safety limits. Three noise/model pairs and analytic road variations do not establish broad statistical superiority or physical deployment safety.
Reserved roads include sine180/DLC286 excluded from gate development; original-road confirmation and new-shape results should be distinguished. A native run, teacher diagnostic or PPO pilot is conditional on its preceding frozen checks, never automatic from a favorable mean. No training or native action is launched by this reporter.
