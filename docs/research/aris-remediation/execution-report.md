# Recorded method comparison

Source: `/workspace/lans-aris-fixes/execution-evaluation/episodes.csv`
Metric: `penalized_rmse`. Mean of episode RMSEs, equally aggregated across seed means.

SD is across seed means, not time samples. Repeated deterministic seeds are not independent evidence.
This table is descriptive; method labels alone do not establish causal ablations, significance or safety.

| Scenario | Delay (ms) | Method | Survived / episodes | Seeds | Mean RMSE (m) | Seed-mean SD (m) |
|---|---:|---|---:|---:|---:|---:|
| all | 0 | execution_policy | 1/1 | 1 | 0.009658 | unavailable (one seed) |
| all | 0 | lqr | 1/1 | 1 | 0.009559 | unavailable (one seed) |
| all | 10 | execution_policy | 1/1 | 1 | 0.009559 | unavailable (one seed) |
| all | 10 | lqr | 1/1 | 1 | 0.009559 | unavailable (one seed) |
| all | 100 | execution_policy | 1/1 | 1 | 0.009559 | unavailable (one seed) |
| all | 100 | lqr | 1/1 | 1 | 0.009559 | unavailable (one seed) |
| all | 20 | execution_policy | 1/1 | 1 | 0.009559 | unavailable (one seed) |
| all | 20 | lqr | 1/1 | 1 | 0.009559 | unavailable (one seed) |
