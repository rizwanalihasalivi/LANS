# Current student/teacher headroom check

Post-hoc descriptive recomputation of the existing revision8 paired evaluation; no new episodes, training, model selection or controller changes. Inputs: `integrations/webots/results/revision8-student/evaluation/episodes.csv`. This previously inspected evaluation is not a development tuning set.

| Region | Student improvement vs LQR | Teacher improvement vs LQR | Teacher improvement vs student |
|---|---:|---:|---:|
| overall | 2.158% | 2.231% | +0.074% |
| nominal | 3.589% | 3.660% | +0.074% |
| tire_mismatch | 1.513% | 1.468% | -0.046% |
| low_friction | 2.121% | 2.250% | +0.132% |
| sensor_stress | 3.209% | 3.695% | +0.501% |
| latency20 | 3.689% | 3.682% | -0.008% |
| latency100 | 0.000% | 0.000% | +0.000% |

Current expected-cost teacher mean improvement is below5% in every region; its three paired seed means are also below5% in every region. Its aggregate advantage over the student is only0.074%. Tire mismatch and20ms student means slightly outperform this teacher. These are three optimization/noise pairs, not evidence of a global optimum or independent policy-seed significance.

The existing finite teacher searches five residual proposals over200ms under the actual gate and averages three forecast noise branches. It is privileged and approximate. These results demonstrate little remaining imitation gap to this teacher, not an absolute controller ceiling.

Recommendation: retain the frozen student as the reference. Do not increase PPO budget, authority, or repeatedly reuse this evaluation to tune toward5%. A new development-only protocol should first compare the current200ms teacher to a prespecified longer-preview/sequence-aware teacher under unchanged actuator/gate limits. Include paired LQR, fixed correction and student, independent forecast noise, realized closed-loop scoring and failure counts. If useful additional opportunity is demonstrated, examine gate rejection/prediction attribution before deciding whether to change prediction or student training. A larger search can also fail; do not presume it unlocks5%.

Freeze the operating regions and5% target before that experiment. Keep nominal and survival preservation and exact100ms fallback. Any new teacher/predictor selection must use development data; a newly frozen final evaluation follows only after selection. No new diagnostic campaign is launched by this descriptive check.
