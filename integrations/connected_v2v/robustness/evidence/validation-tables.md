# Fresh robustness validation tables

Descriptive results, not final thesis benchmarking.

## Python

| Profile | Passed | Progress / cruise distance (median; min–max) | Max stopped time | Correct-target spacing RMS (median; max) | Censored stable return |
| --- | --- | --- | --- | --- | --- |
| burst_misses | 30/30 | 0.918; 0.894–1.007 | 0.20 s | 62.81; 69.90 m | 0/30 |
| combined | 30/30 | 0.699; 0.413–0.949 | 5.70 s | 133.00; 187.36 m | 1/30 |
| curved | 30/30 | 0.896; 0.848–0.922 | 0.00 s | 62.06; 66.95 m | 0/30 |
| dense_curved | 30/30 | 0.918; 0.894–1.004 | 0.00 s | 62.14; 66.88 m | 0/30 |
| dual_blackout | 30/30 | 0.896; 0.849–0.923 | 0.35 s | 64.25; 68.37 m | 0/30 |
| noisy_nonconnected | 30/30 | 0.903; 0.850–0.979 | 0.55 s | 66.11; 80.24 m | 0/30 |
| occlusion_brake | 30/30 | 0.880; 0.687–0.942 | 0.00 s | 70.17; 134.18 m | 0/30 |
| v2v_blackout | 30/30 | 0.897; 0.849–0.923 | 0.00 s | 62.09; 66.22 m | 0/30 |

## Native Webots

| Profile | Passed | Progress / cruise distance (median; min–max) | Max stopped time | Correct-target spacing RMS (median; max) | Censored stable return |
| --- | --- | --- | --- | --- | --- |
| burst_misses | 6/6 | 0.864; 0.845–0.927 | 0.35 s | 55.56; 58.07 m | 0/6 |
| curved | 6/6 | 0.855; 0.846–0.864 | 0.25 s | 55.07; 57.71 m | 0/6 |
| dense_curved | 6/6 | 0.856; 0.845–0.868 | 0.35 s | 56.50; 59.64 m | 0/6 |
| dual_blackout | 6/6 | 0.855; 0.846–0.864 | 0.85 s | 57.39; 59.71 m | 0/6 |
| noisy_nonconnected | 6/6 | 0.847; 0.719–0.864 | 0.35 s | 63.89; 136.56 m | 0/6 |
| occlusion_brake | 6/6 | 0.842; 0.816–0.849 | 0.35 s | 65.22; 68.40 m | 0/6 |

Progress is measured movement divided by configured cruise distance. Target reacquisition and nominal headway settling are different: full spacing and stop/censoring data remain in every raw episode and summary. Neighbor observations provide exit evidence only; normal following still requires fresh local radar or V2V state.
