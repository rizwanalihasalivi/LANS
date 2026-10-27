# Campaign interpretation

| Method | Lateral RMSE (m) | Gain versus LQR | Heading RMSE (rad) | Steering-rate RMS (rad/s) | Survival |
|---|---:|---:|---:|---:|---:|
| lqr | 0.090578 | 0.000% | 0.020024 | 0.069169 | 96/96 |
| fixed_negative | 0.093213 | -2.909% | 0.020279 | 0.069490 | 96/96 |
| fixed_positive | 0.093213 | -2.909% | 0.020279 | 0.069490 | 96/96 |
| student | 0.090599 | -0.024% | 0.020027 | 0.069213 | 96/96 |
| scratch | 0.092441 | -2.057% | 0.020218 | 0.069551 | 96/96 |
| finetune | 0.090618 | -0.044% | 0.020029 | 0.069243 | 96/96 |
| fixed_authority | 0.099658 | -10.024% | 0.022049 | 0.147717 | 95/96 |
| latency_gain | 0.085469 | 5.640% | 0.020310 | 0.120488 | 96/96 |
| no_recovery | 0.090637 | -0.066% | 0.020032 | 0.069265 | 96/96 |

Development eligibility: **False**. finetune lacks >=1% improvement vs lqr; finetune lacks >=1% improvement vs student; pair0 does not improve student; pair1 does not improve student; pair2 does not improve student.

Actual-worker campaign: 10500 ticks, 985 deadline misses (9.381%), functional pass:True. Learned authority was active on 0 ticks; this provides no real-worker learning-benefit evidence.

Native interface verification:True; observed native wall timing:False. Resource-partition diagnostic functional pass:True; observed timing pass:False. Partitioned generated load does not exclude host OS activity, replace original failures or establish WCET.

See the frozen protocol, raw traces, independent audits and completion-matrix.md. Reserved confirmation remains unopened when development fails.

The manuscript-inspired latency-gain comparator reduces lateral RMSE by 5.640%, but increases heading RMSE by 1.428% and steering-rate RMS by 74.192%. This exceeds the predefined5% smoothness tradeoff limit. Fixed authority loses one episode under20ms service. The simple gain is a promising descriptive tracking result, not a selected balanced winner. Same-gain student/constant controls and separate native/timing validation would be needed to attribute its benefit to additional PPO learning. The proposed predictive supervisor did not retain that tracking gain; no post-result gate tuning or reserved-test opening was performed.

See deadline-diagnosis.json for observed scheduling/processing decomposition; no causal OS/WCET guarantee is inferred.
