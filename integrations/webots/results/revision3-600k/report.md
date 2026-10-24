# Baseline600k confirmation: development learning trend

Two existing300k baseline checkpoints continued for300k additional steps each. Both now contain600k total steps; no larger-network run, five-seed full training, final reserved evaluation or native transfer was performed.

| Checkpoint | Seed101 RMSE (m) | Seed202 RMSE (m) | Mean RMSE (m) | Survived /72 |
|---|---:|---:|---:|---:|
| 100k | 0.084147 | 0.083799 | 0.083973 | 72 |
| 300k | 0.084565 | 0.083894 | 0.084229 | 72 |
| 600k | 0.084579 | 0.083607 | 0.084093 | 72 |

| Region | 100k baseline | 300k baseline | 600k baseline | 600k change vs300k | LQR | Old-rescaled gated | Legacy gated |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 0.062390 | 0.062542 | 0.062138 | -0.65% | 0.062838 | 0.062607 | 0.060914 |
| tire_mismatch | 0.174440 | 0.174915 | 0.174916 | +0.00% | 0.175158 | 0.174790 | 0.172808 |
| low_friction | 0.081440 | 0.081674 | 0.081602 | -0.09% | 0.082062 | 0.081755 | 0.080499 |
| sensor_stress | 0.060804 | 0.061249 | 0.061225 | -0.04% | 0.061022 | 0.060774 | 0.059753 |
| latency20 | 0.061892 | 0.062124 | 0.061805 | -0.51% | 0.062617 | 0.062406 | 0.060668 |
| latency100 | 0.062871 | 0.062871 | 0.062871 | +0.00% | 0.062871 | 0.062871 | 0.062871 |

## Frozen progress criteria

Overall change600k vs300k: **-0.162%**. Versus old-rescaled: **-0.128%**. Negative favors600k.

| Check | Passed |
|---|---|
| improves_300k_by_1pct | False |
| beats_old_rescaled_by_1pct | False |
| both_seeds_improve | False |
| regional_consistency | True |
| nominal_preservation | True |
| survival | True |

Material improving trend under all predeclared operational checks: **False**. Full training remains unapproved.

These checks require ≥1% improvement against both300k and the old-rescaled anchor, better means for both seeds, improvement in at least4/5 active regions with no region >1% worse, preserved nominal accuracy and survival. They are budget-review thresholds, not statistical significance or a convergence proof. All per-region values and both seed means remain visible even if the rule fails.

## Provenance and limits

Raw grid verified:288 episodes. All216 reference cells exactly reproduced the previous development errors/survival. Optimizer counters advance15000→30000 and normalization counts300k→600k; completed episode-step counts leave only valid unfinished tails. Initial and final model/source hashes are recorded.

Saved weights, Adam and reward normalization continue; simulator environments restart with SB3 model.seed+i, explicitly matching the prior effective behavior. This is not bit-for-bit uninterrupted600k training. The curve has three measured development checkpoints, not a dense convergence trajectory.

The same two training seeds, paths and development noise are repeatedly consulted at the user’s request. No reserved generalization claim follows. Legacy references have1M training steps and different model seeds0/1, while new policies use101/202. Their comparison does not isolate architecture/training benefit at matched budgets. Gate, ±.08 candidate range, reward and network remain unchanged. A plateau in these checks would not prove no future learning is possible, but it weakens the case for spending five million steps on this route.
