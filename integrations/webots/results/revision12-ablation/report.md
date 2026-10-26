# Revision12 predictor / objective development ablation

Source freeze: `c49ddc065caf9c93eb4867b91446a8037a11ffc7` (from completion record). All 1080 paired development episodes and archived source digests are validated. The completion record declares zero training steps and an unopened reserved split; this reporter reads only this development run and launches no training.

## Overall raw results

| Method | Survival /108 | Mean penalized RMSE (m) | Paired seed-mean SD | Reduction vs LQR |
|---|---:|---:|---:|---:|
| lqr | 108 | 0.08424021 | 0.00006575 | +0.000% |
| legacy_fixed_m004 | 108 | 0.08355876 | 0.00003915 | +0.809% |
| legacy_fixed_p004 | 108 | 0.08392361 | 0.00004876 | +0.376% |
| legacy_student | 108 | 0.08259318 | 0.00005825 | +1.955% |
| preview_fixed_m004 | 108 | 0.08331620 | 0.00000804 | +1.097% |
| preview_fixed_p004 | 108 | 0.08366838 | 0.00008588 | +0.679% |
| preview_student | 108 | 0.08211425 | 0.00006828 | +2.524% |
| lateral_fixed_m004 | 108 | 0.07845764 | 0.00009412 | +6.864% |
| lateral_fixed_p004 | 108 | 0.07655554 | 0.00004633 | +9.122% |
| lateral_student | 108 | 0.08042610 | 0.00046231 | +4.528% |

## Regional raw mean RMSE

| Region | lqr | legacy_fixed_m004 | legacy_fixed_p004 | legacy_student | preview_fixed_m004 | preview_fixed_p004 | preview_student | lateral_fixed_m004 | lateral_fixed_p004 | lateral_student |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| nominal | 0.06266488 | 0.06175970 | 0.06215833 | 0.06052375 | 0.06136480 | 0.06192172 | 0.06002962 | 0.05754981 | 0.05682195 | 0.05856214 |
| tire_mismatch | 0.17492710 | 0.17393560 | 0.17451239 | 0.17261283 | 0.17370998 | 0.17399275 | 0.17182627 | 0.16026772 | 0.15447107 | 0.16735149 |
| low_friction | 0.08100468 | 0.08024617 | 0.08067932 | 0.07925938 | 0.07998773 | 0.08040667 | 0.07884410 | 0.07360932 | 0.07140495 | 0.07733018 |
| sensor_stress | 0.06094273 | 0.06048468 | 0.06083630 | 0.05945578 | 0.06022225 | 0.06072957 | 0.05891229 | 0.05766670 | 0.05601562 | 0.05794083 |
| latency20 | 0.06294562 | 0.06197012 | 0.06239907 | 0.06075107 | 0.06165615 | 0.06200332 | 0.06011696 | 0.05869598 | 0.05766336 | 0.05841568 |
| latency100 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 | 0.06295628 |

## Paired seed raw mean RMSE

| Student seed / noise pair | lqr | legacy_fixed_m004 | legacy_fixed_p004 | legacy_student | preview_fixed_m004 | preview_fixed_p004 | preview_student | lateral_fixed_m004 | lateral_fixed_p004 | lateral_student |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 701 / 0 | 0.08426693 | 0.08360395 | 0.08397078 | 0.08266001 | 0.08331915 | 0.08374713 | 0.08219084 | 0.07835159 | 0.07660901 | 0.08073522 |
| 802 / 1 | 0.08416531 | 0.08353532 | 0.08387340 | 0.08255314 | 0.08330710 | 0.08357680 | 0.08205973 | 0.07853127 | 0.07653033 | 0.08064845 |
| 903 / 2 | 0.08428841 | 0.08353700 | 0.08392666 | 0.08256640 | 0.08332234 | 0.08368121 | 0.08209219 | 0.07849005 | 0.07652728 | 0.07989462 |

## Frozen screens

| Variant | Gate progress | Learning benefit vs both constants | Eligible | Regional 5% target | Overall 5% reduction |
|---|---|---|---|---|---|
| preview | False | True | False | False | False |
| lateral | True | False | False | False | False |

preview failed gate checks: overall_gain_vs_legacy_student, minimum_stress_regions_with_one_percent_gain.
preview failed learned-benefit checks: none.
preview qualifying 5% stress regions (each lower in all three pairs): none.


lateral failed gate checks: none.
lateral failed learned-benefit checks: one_percent_gain_vs_fixed_m004, one_percent_gain_vs_fixed_p004.
lateral qualifying 5% stress regions (each lower in all three pairs): none.


Selected gate: **none**. No variant passes both gate progress and learned-benefit screens.

No variant qualifies. Stop the retraining path at this development screen; additional RL steps 0 and reserved split unopened.

## Limits

The original student weights and train-only standardizer remain frozen. Changing a gate changes the 20-feature history distribution even when feature names and actor weights are identical; this comparison isolates gate changes, not a newly trained deployment-matched policy.
Three optimization/noise pairs and known geometry/condition families are descriptive evidence, not independent-domain generalization or statistical proof. Mean episode penalized RMSE fills failed unexecuted tails with 2.5 m; failed cases remain in denominators. Severe 100 ms equality is fallback, not an AI win.
The regional 5% target and overall 5% reduction are reported separately from gate-progress/learning-benefit eligibility. Undefined reductions against a zero reference are stored as null and cannot pass a gain threshold. A lower predictor cost or changed gate alone does not establish learning-specific benefit, real-vehicle safety, stability, native timing or superiority to published controllers.
