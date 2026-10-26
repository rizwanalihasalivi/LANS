# Revision 12 posthoc trace tradeoff diagnostic

Existing development traces only: repetition 0 / student seed 701, 25 m/s, dlc220, one trajectory per method in each of six regions. This is not a tradeoff analysis of all 108 paired cells, an independent replication, a predeclared selection criterion, or a safety proof. No new rollouts, training, tuning, policy loading or reserved-split access.

Heading error is true post-step heading minus the path heading computed at the same post-step x by the frozen core path_values function. Command RMS uses each issued command. Actuator rate is (delta[t]-delta[t-1])/0.01 s, including the known initial delta[-1]=0. Total variation sums all absolute actuator increments, including the first. Every trace has 1080 samples (10.8 s) and is complete. Aggregates below are arithmetic means of episode metrics; relative changes compare those means to LQR, rather than averaging regional percentages.

## Six-region mean episode metrics

| Method | Lateral RMSE (m) | Heading RMSE (rad) | Command RMS (rad) | Actuator rate RMS (rad/s) | Actuator TV (rad) |
|---|---:|---:|---:|---:|---:|
| lqr | 0.100773 | 0.027422 | 0.027461 | 0.112594 | 0.887933 |
| legacy_student | 0.100417 | 0.027382 | 0.027767 | 0.128168 | 1.081378 |
| preview_student | 0.099196 | 0.027144 | 0.027534 | 0.127342 | 1.076303 |
| lateral_student | 0.097787 | 0.027026 | 0.028428 | 0.153489 | 1.317838 |
| lateral_fixed_p004 | 0.093692 | 0.028733 | 0.029299 | 0.128476 | 1.061007 |
| lateral_fixed_m004 | 0.093077 | 0.028128 | 0.028836 | 0.127586 | 1.048062 |

## Percent change versus LQR (negative is lower)

| Method | Lateral RMSE | Heading RMSE | Command RMS | Actuator rate RMS | Actuator TV |
|---|---:|---:|---:|---:|---:|
| legacy_student | -0.353% | -0.144% | +1.114% | +13.832% | +21.786% |
| preview_student | -1.564% | -1.013% | +0.266% | +13.099% | +21.214% |
| lateral_student | -2.963% | -1.444% | +3.520% | +36.321% | +48.416% |
| lateral_fixed_p004 | -7.026% | +4.779% | +6.695% | +14.105% | +19.492% |
| lateral_fixed_m004 | -7.636% | +2.573% | +5.009% | +13.315% | +18.034% |

## Regional percent change versus LQR

| Region | Method | Lateral RMSE | Heading RMSE | Command RMS | Actuator rate RMS | Actuator TV |
|---|---|---:|---:|---:|---:|---:|
| nominal | legacy_student | -1.064% | -0.902% | -0.660% | +13.545% | +25.578% |
| nominal | preview_student | -2.050% | -1.458% | -0.880% | +13.036% | +24.958% |
| nominal | lateral_student | -9.613% | -4.974% | +2.968% | +57.515% | +77.102% |
| nominal | lateral_fixed_p004 | -13.024% | +3.390% | +6.180% | +16.227% | +23.413% |
| nominal | lateral_fixed_m004 | -12.769% | +1.104% | +3.708% | +13.662% | +21.741% |
| tire_mismatch | legacy_student | +1.375% | +1.651% | +3.648% | +20.386% | +29.305% |
| tire_mismatch | preview_student | +0.175% | +0.404% | +1.945% | +17.054% | +25.616% |
| tire_mismatch | lateral_student | +0.833% | +1.180% | +3.909% | +36.710% | +52.679% |
| tire_mismatch | lateral_fixed_p004 | -2.665% | +8.583% | +10.840% | +19.338% | +24.302% |
| tire_mismatch | lateral_fixed_m004 | -4.456% | +6.469% | +8.032% | +14.374% | +19.153% |
| low_friction | legacy_student | -1.436% | -1.079% | +0.146% | +14.912% | +23.854% |
| low_friction | preview_student | -2.678% | -1.952% | -0.246% | +12.714% | +20.766% |
| low_friction | lateral_student | -4.228% | -2.858% | +2.125% | +39.342% | +50.093% |
| low_friction | lateral_fixed_p004 | -11.046% | +7.717% | +8.354% | +13.720% | +18.574% |
| low_friction | lateral_fixed_m004 | -13.671% | +3.133% | +6.464% | +17.454% | +21.288% |
| sensor_stress | legacy_student | -1.806% | -0.398% | +2.814% | +20.110% | +27.633% |
| sensor_stress | preview_student | -4.908% | -2.277% | +0.545% | +21.859% | +31.490% |
| sensor_stress | lateral_student | -2.847% | +0.379% | +10.743% | +51.996% | +64.415% |
| sensor_stress | lateral_fixed_p004 | -11.719% | +3.552% | +8.676% | +23.783% | +30.446% |
| sensor_stress | lateral_fixed_m004 | -8.983% | +2.513% | +10.089% | +26.905% | +31.084% |
| latency20 | legacy_student | -1.664% | -1.048% | -0.467% | +11.946% | +21.163% |
| latency20 | preview_student | -2.602% | -1.516% | -0.591% | +12.638% | +22.588% |
| latency20 | lateral_student | -7.267% | -3.640% | +1.456% | +31.346% | +44.064% |
| latency20 | lateral_fixed_p004 | -9.632% | +2.717% | +3.706% | +9.903% | +18.193% |
| latency20 | lateral_fixed_m004 | -9.166% | -0.141% | +0.021% | +6.411% | +13.525% |
| latency100 | legacy_student | +0.000% | +0.000% | +0.000% | +0.000% | +0.000% |
| latency100 | preview_student | +0.000% | +0.000% | +0.000% | +0.000% | +0.000% |
| latency100 | lateral_student | +0.000% | +0.000% | +0.000% | +0.000% | +0.000% |
| latency100 | lateral_fixed_p004 | +0.000% | +0.000% | +0.000% | +0.000% | +0.000% |
| latency100 | lateral_fixed_m004 | +0.000% | +0.000% | +0.000% | +0.000% | +0.000% |

## Interpretation

On this representative subset, lateral_fixed_p004 changes lateral RMSE by -7.026%, but heading RMSE by +4.779%, command RMS by +6.695%, actuator-rate RMS by +14.105%, and actuator TV by +19.492%.

For lateral_student the corresponding changes are -2.963%, -1.444%, +3.520%, +36.321%, and +48.416%.

The student's largest actuator-motion cost is nominal: rate RMS +57.515% and TV +77.102%. In sensor stress, lateral_student has rate RMS +51.996% and TV +64.415%. There preview_student improves lateral RMSE more (-4.908% versus -2.847%) and has lower heading RMSE, command RMS, actuator-rate RMS and TV than lateral_student. The nominal rate cap is respected, but a shared maximum-rate bound does not imply shared smoothness.

The positive constant increases heading RMSE in all five active regions, peaking at +8.583% in tire mismatch, while lowering lateral RMSE in each. The negative constant has lower mean lateral RMSE than the positive constant on this particular subset; this is an illustration of limited subset representativeness, not a basis for selecting either sign.

The lateral-only objective drops heading/yaw/steering-effort terms, so improved lateral error alone cannot establish a multi-objective improvement. These descriptive measurements cannot assign all differences causally to individual cost terms because gate acceptance and subsequent state histories change.

The latency100 metrics match LQR exactly for every method, consistent with severe-delay fallback. Excluding latency100, the five-active-region changes for lateral_fixed_p004 are lateral_rmse_m -8.067%, heading_rmse_rad +5.616%, command_rms_rad +7.878%, actuator_rate_rms_rad_s +16.703%, actuator_total_variation_rad +23.031%.

Full-grid primary outcome and predeclared selection are separate: the known 1080-episode result is 9.122% lower mean penalized lateral RMSE for lateral_fixed_p004 and 4.528% for lateral_student versus LQR, with no learned variant passing predeclared selection. This diagnostic does not alter that decision or justify opening the reserved split.

The JSON includes all ten methods, all six regions, input SHA-256 hashes, metric definitions, validation residuals, and separate all-six/five-active aggregates. Regenerate with:

```sh
python /tmp/lans-v12-tradeoffs.py --repo /workspace/LANS-webots --output /tmp/lans-v12-tradeoffs.json
```
