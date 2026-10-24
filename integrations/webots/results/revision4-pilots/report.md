# Gate-aware / relative-reward pilot results

**800,000 pilot steps**: four arms × two seeds ×100k. **504 paired development episodes**. Frozen gate and old checkpoints unchanged; final reserved tests and five-seed full training not run.

| Arm | Training gate | Relative reward | Domain randomization |
|---|---|---|---|
| A | No | No | No |
| B | Yes | No | No |
| C | No | Yes | No |
| D | Yes | Yes | Yes |

All A–D policies are residual ±0.08-rad policies and are evaluated inside the same frozen performance gate. The standalone full-command reference is a different, frozen1M-step model, never a residual output repurposed as full steering.

| Region | Method | Survived /12 | Mean penalized RMSE (m) | Gate-active ticks |
|---|---|---:|---:|---:|
| nominal | lqr | 12 | 0.063117 | 0.00% |
| nominal | standalone_full_reference | 12 | 0.092676 | — |
| nominal | legacy_gated_reference | 12 | 0.061223 | 12.30% |
| nominal | A_hybrid | 12 | 0.062454 | 7.91% |
| nominal | B_hybrid | 12 | 0.063020 | 3.00% |
| nominal | C_hybrid | 12 | 0.062916 | 6.58% |
| nominal | D_hybrid | 12 | 0.063097 | 2.60% |
| tire_mismatch | lqr | 12 | 0.174511 | 0.00% |
| tire_mismatch | standalone_full_reference | 12 | 0.165251 | — |
| tire_mismatch | legacy_gated_reference | 12 | 0.172033 | 6.37% |
| tire_mismatch | A_hybrid | 12 | 0.173859 | 4.26% |
| tire_mismatch | B_hybrid | 12 | 0.174409 | 1.88% |
| tire_mismatch | C_hybrid | 12 | 0.174379 | 3.42% |
| tire_mismatch | D_hybrid | 12 | 0.174503 | 1.98% |
| low_friction | lqr | 12 | 0.081536 | 0.00% |
| low_friction | standalone_full_reference | 12 | 0.106836 | — |
| low_friction | legacy_gated_reference | 12 | 0.080137 | 10.50% |
| low_friction | A_hybrid | 12 | 0.081123 | 6.79% |
| low_friction | B_hybrid | 12 | 0.081601 | 2.60% |
| low_friction | C_hybrid | 12 | 0.081352 | 6.29% |
| low_friction | D_hybrid | 12 | 0.081612 | 2.92% |
| sensor_stress | lqr | 12 | 0.060837 | 0.00% |
| sensor_stress | standalone_full_reference | 12 | 0.092539 | — |
| sensor_stress | legacy_gated_reference | 12 | 0.059207 | 12.53% |
| sensor_stress | A_hybrid | 12 | 0.060656 | 7.72% |
| sensor_stress | B_hybrid | 12 | 0.060772 | 2.85% |
| sensor_stress | C_hybrid | 12 | 0.060740 | 6.63% |
| sensor_stress | D_hybrid | 12 | 0.060773 | 2.92% |
| latency20 | lqr | 12 | 0.062873 | 0.00% |
| latency20 | standalone_full_reference | 12 | 0.092758 | — |
| latency20 | legacy_gated_reference | 12 | 0.060969 | 13.50% |
| latency20 | A_hybrid | 12 | 0.062185 | 9.08% |
| latency20 | B_hybrid | 12 | 0.062807 | 3.09% |
| latency20 | C_hybrid | 12 | 0.062608 | 7.56% |
| latency20 | D_hybrid | 12 | 0.062864 | 2.84% |
| latency100 | lqr | 12 | 0.062646 | 0.00% |
| latency100 | standalone_full_reference | 0 | 2.226001 | — |
| latency100 | legacy_gated_reference | 12 | 0.062646 | 0.00% |
| latency100 | A_hybrid | 12 | 0.062646 | 0.00% |
| latency100 | B_hybrid | 12 | 0.062646 | 0.00% |
| latency100 | C_hybrid | 12 | 0.062646 | 0.00% |
| latency100 | D_hybrid | 12 | 0.062646 | 0.00% |

## Overall and paired arm comparisons

| Method | Survived /72 | Mean RMSE score (m) | Change vs LQR | Seed101 change vs A | Seed202 change vs A |
|---|---:|---:|---:|---:|---:|
| lqr | 72 | 0.084253 | +0.00% | +0.27% | +0.76% |
| standalone_full_reference | 60 | 0.462677 | +449.15% | +452.98% | +450.98% |
| legacy_gated_reference | 72 | 0.082702 | -1.84% | -1.37% | -1.30% |
| A_hybrid | 72 | 0.083821 | -0.51% | +0.00% | +0.00% |
| B_hybrid | 72 | 0.084209 | -0.05% | +0.36% | +0.57% |
| C_hybrid | 72 | 0.084107 | -0.17% | +0.22% | +0.47% |
| D_hybrid | 72 | 0.084249 | -0.01% | +0.34% | +0.68% |

## Training diagnostics

Fractions/bonuses below are weighted by steps in completed episodes; unfinished tails are excluded. For ungated A/C, execution fraction1 means residual pass-through, not supervisor acceptance.

| Arm | Seed | Completed episodes | Training execution fraction | Mean relative bonus | Friction range | Stiffness scale range | Delayed episodes |
|---|---:|---:|---:|---|---|---:|
| A | 101 | 121 | 100.00% | +0.0000000 | [0.9, 0.9] | [1.0, 1.0] | 0.00% |
| A | 202 | 122 | 100.00% | +0.0000000 | [0.9, 0.9] | [1.0, 1.0] | 0.00% |
| B | 101 | 121 | 1.04% | +0.0000000 | [0.9, 0.9] | [1.0, 1.0] | 0.00% |
| B | 202 | 121 | 1.43% | +0.0000000 | [0.9, 0.9] | [1.0, 1.0] | 0.00% |
| C | 101 | 121 | 100.00% | -0.0011906 | [0.9, 0.9] | [1.0, 1.0] | 0.00% |
| C | 202 | 121 | 100.00% | -0.0019653 | [0.9, 0.9] | [1.0, 1.0] | 0.00% |
| D | 101 | 120 | 0.95% | +0.0000097 | [0.6055861686938475, 0.9] | [0.653839318592547, 1.0] | 37.50% |
| D | 202 | 120 | 0.64% | +0.0000075 | [0.6073361428396776, 0.9] | [0.6502800055478966, 1.0] | 39.17% |

## Predeclared extension decision

| Arm | Overall mean RMSE | Stress mean RMSE | Eligible | Failed checks |
|---|---:|---:|---|---|
| B | 0.084209 | 0.105594 | False | overall_vs_A, both_seeds_vs_A, two_stress_regions, both_seed_stress_means |
| C | 0.084107 | 0.105491 | False | overall_vs_A, both_seeds_vs_A, two_stress_regions, both_seed_stress_means |
| D | 0.084249 | 0.105629 | False | overall_vs_A, both_seeds_vs_A, two_stress_regions, both_seed_stress_means |

Selected for300k extension: **none**.

The100k extension screen requires ≥1% overall improvement over A with both seed means better, ≥1% LQR improvement in at least2/3 stress regions, both seed stress means better than LQR, no active region >1% worse than LQR, nominal/survival preservation and exact severe-delay fallback. These are predeclared development spending criteria, not statistical significance.

No arm met all promising-pilot criteria. No300k extension or full-budget training was launched; no criteria were relaxed after inspecting results.

## Reserved allocation correction

No reserved evaluation was run. The original proposed base8100000 overlaps36 development IDs under the shared seed-index formula (pilot seed202 versus future seed2). Before any reserved use, `reserved_split.json` replaces that unused allocation with base91000000 and records the explicit disjoint72 development/180 future reserved IDs. Pilot/controller sources and actual development data are unchanged.

## Interpretation and limits

B−A isolates training with the frozen gate; C−A isolates the added relative-reward term. D is a combined package including gate, relative reward, domain randomization and randomized-course feasibility screening. A D improvement cannot be attributed to domain randomization alone; this is not a complete factorial ablation.

Relative reward is training-only privileged simulation: two100ms branches start at the same true state/plant parameters, differ only in the first10ms executed command, then use identical true-state nominal LQR continuation. It consumes no sensor RNG, does not alter the real transition and provides exactly zero bonus when the executed command equals LQR. It is a surrogate counterfactual, not measured future benefit or an actor input.

Training is synchronous. The sampled action is transformed by the actual gate before the transition, so PPO receives reward for that action’s gated execution. No newly sampled action is assigned the reward of an older queued action. Deployment service-delay experiments remain a separate frozen-policy test; only sensor delay is randomized during training. The actor keeps the same9 observations and does not observe gate memory or hidden friction/stiffness, so partial observability remains.

Only two short-run training seeds, known geometries and development noise are used. Old full-command and residual references have different seeds and1M budgets. Do not interpret their comparison as an equal-budget architecture test or infer full-command capability from residual results. Failure-penalized scores include a2.5m unexecuted-tail fill; failed episodes remain in denominators. No native transfer, real-time, stability, convergence or real-vehicle safety claim is made.
