# Revision13 confirmation results

Executable freeze: `583ee07e1ec8f8ce61eb457796e301f8dd9750ac`. Verified 2160 complete-grid episode records, archived source hashes, metric arithmetic, physical bounds and severe-delay fallback. Additional training steps: 0.

Each method has 432 paired cells. Mirrored orientations share transformed noise and initial errors; they are correlated symmetry checks, not additional independent seeds. Means give equal weight to episodes.

## Overall metrics

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 432/432 | 0.06914495 | 0.01499757 | 0.06102246 | 0.50674972 | +0.000% |
| legacy_student | 432/432 | 0.06781289 | 0.01481963 | 0.08924047 | 0.83222054 | +1.926% |
| lateral_fixed_m004 | 432/432 | 0.06427074 | 0.01512248 | 0.08332181 | 0.75416214 | +7.049% |
| lateral_fixed_p004 | 432/432 | 0.06427074 | 0.01512248 | 0.08332181 | 0.75416214 | +7.049% |
| lateral_student | 432/432 | 0.06629175 | 0.01488971 | 0.12358883 | 1.23100557 | +4.126% |

## Replication subset: original_positive

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 108/108 | 0.08442789 | 0.01900366 | 0.06731227 | 0.55752931 | +0.000% |
| legacy_student | 108/108 | 0.08275559 | 0.01875282 | 0.09270470 | 0.83852236 | +1.981% |
| lateral_fixed_m004 | 108/108 | 0.07864162 | 0.01913401 | 0.08797727 | 0.78020851 | +6.854% |
| lateral_fixed_p004 | 108/108 | 0.07671916 | 0.01914547 | 0.08885561 | 0.79289345 | +9.131% |
| lateral_student | 108/108 | 0.08097588 | 0.01870024 | 0.12135717 | 1.14553042 | +4.089% |

## Replication subset: original_mirrored

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 108/108 | 0.08442789 | 0.01900366 | 0.06731227 | 0.55752931 | +0.000% |
| legacy_student | 108/108 | 0.08275358 | 0.01875197 | 0.09274795 | 0.83777835 | +1.983% |
| lateral_fixed_m004 | 108/108 | 0.07671916 | 0.01914547 | 0.08885561 | 0.79289345 | +9.131% |
| lateral_fixed_p004 | 108/108 | 0.07864162 | 0.01913401 | 0.08797727 | 0.78020851 | +6.854% |
| lateral_student | 108/108 | 0.08099260 | 0.01872427 | 0.12129133 | 1.14534956 | +4.069% |

## Replication subset: new_positive

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 108/108 | 0.05386200 | 0.01099148 | 0.05473266 | 0.45597013 | +0.000% |
| legacy_student | 108/108 | 0.05287629 | 0.01088682 | 0.08570707 | 0.82484885 | +1.830% |
| lateral_fixed_m004 | 108/108 | 0.05132588 | 0.01108505 | 0.07631056 | 0.69576243 | +4.709% |
| lateral_fixed_p004 | 108/108 | 0.05039630 | 0.01112541 | 0.08014378 | 0.74778416 | +6.434% |
| lateral_student | 108/108 | 0.05156770 | 0.01102374 | 0.12580836 | 1.31527008 | +4.260% |

## Replication subset: new_mirrored

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 108/108 | 0.05386200 | 0.01099148 | 0.05473266 | 0.45597013 | +0.000% |
| legacy_student | 108/108 | 0.05286610 | 0.01088691 | 0.08580215 | 0.82773262 | +1.849% |
| lateral_fixed_m004 | 108/108 | 0.05039630 | 0.01112541 | 0.08014378 | 0.74778416 | +6.434% |
| lateral_fixed_p004 | 108/108 | 0.05132588 | 0.01108505 | 0.07631056 | 0.69576243 | +4.709% |
| lateral_student | 108/108 | 0.05163081 | 0.01111058 | 0.12589846 | 1.31787222 | +4.142% |

Exact-match original-positive replication screen: **True**.
This screen concerns the fixed +0.04 correction and the original positive-orientation roads. The full eight-road mean is a different distribution from the earlier 9.122% figure. Confirmation does not select a controller.

## Region: nominal

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05362522 | 0.01325469 | 0.05932229 | 0.47995564 | +0.000% |
| legacy_student | 72/72 | 0.05198138 | 0.01300289 | 0.09529487 | 0.88544882 | +3.065% |
| lateral_fixed_m004 | 72/72 | 0.05012077 | 0.01327332 | 0.08900150 | 0.80338040 | +6.535% |
| lateral_fixed_p004 | 72/72 | 0.05012077 | 0.01327332 | 0.08900150 | 0.80338040 | +6.535% |
| lateral_student | 72/72 | 0.05053345 | 0.01302040 | 0.14125313 | 1.41651876 | +5.766% |

## Region: tire_mismatch

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.13653604 | 0.02224815 | 0.06418768 | 0.54584769 | +0.000% |
| legacy_student | 72/72 | 0.13442555 | 0.02205481 | 0.09080128 | 0.86468468 | +1.546% |
| lateral_fixed_m004 | 72/72 | 0.12162517 | 0.02262182 | 0.08970194 | 0.83202664 | +10.921% |
| lateral_fixed_p004 | 72/72 | 0.12162517 | 0.02262182 | 0.08970194 | 0.83202664 | +10.921% |
| lateral_student | 72/72 | 0.13015582 | 0.02183154 | 0.12436940 | 1.22119275 | +4.673% |

## Region: low_friction

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.06462977 | 0.01480487 | 0.06062423 | 0.49778702 | +0.000% |
| legacy_student | 72/72 | 0.06329940 | 0.01458095 | 0.09178567 | 0.86325442 | +2.058% |
| lateral_fixed_m004 | 72/72 | 0.05925408 | 0.01489768 | 0.08933024 | 0.81070551 | +8.318% |
| lateral_fixed_p004 | 72/72 | 0.05925408 | 0.01489768 | 0.08933024 | 0.81070551 | +8.318% |
| lateral_student | 72/72 | 0.06178991 | 0.01462439 | 0.13591306 | 1.37349461 | +4.394% |

## Region: sensor_stress

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05286229 | 0.01317936 | 0.06327312 | 0.55117750 | +0.000% |
| legacy_student | 72/72 | 0.05160789 | 0.01302111 | 0.10750332 | 1.05290742 | +2.373% |
| lateral_fixed_m004 | 72/72 | 0.05045624 | 0.01346805 | 0.09603275 | 0.89966619 | +4.552% |
| lateral_fixed_p004 | 72/72 | 0.05045624 | 0.01346805 | 0.09603275 | 0.89966619 | +4.552% |
| lateral_student | 72/72 | 0.05104449 | 0.01357464 | 0.15620614 | 1.63568371 | +3.439% |

## Region: latency20

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05350727 | 0.01328029 | 0.05946012 | 0.48413953 | +0.000% |
| legacy_student | 72/72 | 0.05185405 | 0.01303995 | 0.09079032 | 0.84543698 | +3.090% |
| lateral_fixed_m004 | 72/72 | 0.05045909 | 0.01325597 | 0.07659705 | 0.69760314 | +5.697% |
| lateral_fixed_p004 | 72/72 | 0.05045909 | 0.01325597 | 0.07659705 | 0.69760314 | +5.697% |
| lateral_student | 72/72 | 0.05051770 | 0.01306921 | 0.12452389 | 1.25755261 | +5.587% |

## Region: latency100

| Method | Survival | Lateral RMSE (m) | Heading RMSE (rad) | Rate RMS (rad/s) | Actuator TV (rad) | Gain vs LQR |
|---|---:|---:|---:|---:|---:|---:|
| lqr | 72/72 | 0.05370910 | 0.01321807 | 0.05926735 | 0.48159095 | +0.000% |
| legacy_student | 72/72 | 0.05370910 | 0.01321807 | 0.05926735 | 0.48159095 | +0.000% |
| lateral_fixed_m004 | 72/72 | 0.05370910 | 0.01321807 | 0.05926735 | 0.48159095 | +0.000% |
| lateral_fixed_p004 | 72/72 | 0.05370910 | 0.01321807 | 0.05926735 | 0.48159095 | +0.000% |
| lateral_student | 72/72 | 0.05370910 | 0.01321807 | 0.05926735 | 0.48159095 | +0.000% |

## Interpretation limits

Heading and lateral tables use declared failure penalties; command, actuator-rate, total-variation and yaw metrics describe executed steps. Failed cases remain in denominators and survival is a separate required check. Full metric sums are stored for every episode; representative traces do not constitute complete telemetry for every case.
Fixed-sign reflection integrity passed 648 paired comparisons at 1e-9 numerical tolerance. Opposite fixed signs should tie globally on the balanced mirror grid; that tie is not evidence of learning. The student need not be reflection-equivariant.
Frozen students retain their original weights and normalization. Student rows are comparators; this stage selects only a nonlearned balanced controller. Engineering heading/smoothness budgets are not certified comfort or safety limits. Three noise/model pairs and analytic road variations do not establish broad statistical superiority or physical deployment safety.
Reserved roads include sine180/DLC286 excluded from gate development; original-road confirmation and new-shape results should be distinguished. A native run, teacher diagnostic or PPO pilot is conditional on its preceding frozen checks, never automatic from a favorable mean. No training or native action is launched by this reporter.
