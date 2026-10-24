# Extended top-two pilot comparison

Stage1 top-two relative gap: 0.310%. Both configurations continued from100k to300k total steps at both pilot seeds. This adds800k steps; cumulative pilot training across both stages is1.6M.

| Region | Method | Survived /12 | Mean penalized RMSE (m) |
|---|---|---:|---:|
| nominal | lqr | 12 | 0.062838 |
| nominal | legacy_gated | 12 | 0.060914 |
| nominal | legacy_rescaled_gated | 12 | 0.062607 |
| nominal | baseline | 12 | 0.062542 |
| nominal | larger_network | 12 | 0.062403 |
| tire_mismatch | lqr | 12 | 0.175158 |
| tire_mismatch | legacy_gated | 12 | 0.172808 |
| tire_mismatch | legacy_rescaled_gated | 12 | 0.174790 |
| tire_mismatch | baseline | 12 | 0.174915 |
| tire_mismatch | larger_network | 12 | 0.175226 |
| low_friction | lqr | 12 | 0.082062 |
| low_friction | legacy_gated | 12 | 0.080499 |
| low_friction | legacy_rescaled_gated | 12 | 0.081755 |
| low_friction | baseline | 12 | 0.081674 |
| low_friction | larger_network | 12 | 0.081830 |
| sensor_stress | lqr | 12 | 0.061022 |
| sensor_stress | legacy_gated | 12 | 0.059753 |
| sensor_stress | legacy_rescaled_gated | 12 | 0.060774 |
| sensor_stress | baseline | 12 | 0.061249 |
| sensor_stress | larger_network | 12 | 0.061250 |
| latency20 | lqr | 12 | 0.062617 |
| latency20 | legacy_gated | 12 | 0.060668 |
| latency20 | legacy_rescaled_gated | 12 | 0.062406 |
| latency20 | baseline | 12 | 0.062124 |
| latency20 | larger_network | 12 | 0.062321 |
| latency100 | lqr | 12 | 0.062871 |
| latency100 | legacy_gated | 12 | 0.062871 |
| latency100 | legacy_rescaled_gated | 12 | 0.062871 |
| latency100 | baseline | 12 | 0.062871 |
| latency100 | larger_network | 12 | 0.062871 |

## Clear-winner checks

| Candidate | Overall RMSE | Change vs other | Seed mean differences (m) | Overall ≥1% | Both seeds | Region consistency | Nominal preserved | Survival | Clear winner |
|---|---:|---:|---|---|---|---|---|---|
| baseline | 0.084229 | -0.10% | [3.85777171403312e-05, -0.00021385527143037708] | False | False | True | True | True | False |
| larger_network | 0.084317 | +0.10% | [-3.85777171403312e-05, 0.00021385527143037708] | False | False | False | True | True | False |

Full training authorized by frozen criteria: **False**. Selected candidate: **none**.

A clear winner requires ≥1% overall improvement over the other candidate, both seed means better, improvement in at least4/5 active regions with no region >1% worse, nominal within2% of LQR, and no regional survival loss. These are operational spending criteria, not a statistical-significance claim. No thresholds are relaxed after seeing results.

Old and old-rescaled policies are frozen1M-step reference models at seeds0/1; pilot models use seeds101/202 and300k total steps. Their noise is paired, but budgets/model seeds differ, so these anchors do not isolate retraining benefit. Final reserved tests remain untouched. Continuation retains policy/optimizer/normalization but restarts environments at SB3 model.seed+i (the constructor offset was overridden; see continuation-audit.json); it is not bit-for-bit uninterrupted300k training.
