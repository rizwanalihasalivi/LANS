# Gate-aware relative-reward pilots

This development experiment tests training changes after range-only retraining plateaued. Protocol and executable sources were frozen in `615274ba8dcdf2c7b88c698afc444e585f127d6c` before the eight pilots. Earlier checkpoints, gate, results and specification are unchanged.

| Arm | Training change relative to A |
|---|---|
| A | Current residual baseline, ±0.08 rad |
| B | Actual frozen revision2 supervisor inside each training transition |
| C | Added reward for a counterfactual improvement over LQR |
| D | B + C + domain randomization and randomized-course feasibility screening |

Each arm uses seeds 101/202, 100,000 steps per seed, eight environments, the same 64×64 network and PPO settings in [protocol.json](protocol.json). All four are evaluated as hybrids through the same frozen gate. B−A and C−A isolate their respective changes; D is a bundled hypothesis, not a full factorial ablation.

## Training semantics

B/D pass the sampled residual through the unchanged performance gate before advancing the plant. Packet age is zero during synchronous training. The sampled action retains its PPO log probability; the gate is an environment transformation. No reward for a queued older command is assigned to a fresh action. This does not train asynchronous service delay; evaluation separately simulates service latency.

C/D add `clip((J_LQR-J_executed)/(1e-4+J_LQR), -1, 1)` to the baseline reward. Two training-only simulated 100 ms branches start from the identical true state and actual plant parameters. They differ in the first 10 ms command, then each follows nominal true-state LQR for 90 ms. Tracking cost integrates `(ey/0.5)^2 + 0.2*(heading_error/0.1)^2` and adds a terminal term. Identical executed/LQR commands give exactly zero bonus. This privileged counterfactual is distinct from the deployment gate predictor, does not mutate the real transition or sensor RNG, and is not measured future benefit.

D draws 25% nominal episodes; otherwise friction is uniform in [0.6,0.9], stiffness scale in [0.65,1], sensor-noise multiplier in [1,2], and sensor delay is 0 or 1 ticks. Randomized sine courses additionally respect the conservative `v²*A*k² <= 0.8*mu*g` amplitude bound. The same nine actor observations are retained: hidden parameters and gate memory are not provided, so partial observability remains.

## Completed results and spending decision

[Full report](../../results/revision4-pilots/report.md), [raw episodes](../../results/revision4-pilots/evaluation/episodes.csv), and [audit](../../results/revision4-pilots/verification.json).

800,000 training steps and 504 development episodes completed. Mean failure-penalized RMSE:

| Method | Mean score (m) | Survived |
|---|---:|---:|
| LQR | 0.084253 | 72/72 |
| Legacy gated residual reference | 0.082702 | 72/72 |
| A hybrid | 0.083821 | 72/72 |
| B hybrid | 0.084209 | 72/72 |
| C hybrid | 0.084107 | 72/72 |
| D hybrid | 0.084249 | 72/72 |
| Frozen standalone full-command reference | 0.462677 | 60/72 |

B/C/D are worse than A in both seed means. None satisfies the predefined extension screen: ≥1% overall improvement over A, improvement in both seeds, ≥1% improvement over LQR in at least two of three stress regions, both seed stress means better than LQR, regional and nominal preservation, survival preservation and exact severe-delay fallback. Therefore no 300k extension was launched. No full training, reserved evaluation or native Webots transfer was performed. Thresholds were not relaxed after results.

All gated hybrids reproduce LQR exactly at simulated 100 ms service delay. The standalone reference fails all twelve severe-delay episodes; its other sixty episodes survive. Failed tails are filled with 2.5 m error in the score. Old full-command/residual references have 1M training steps and different seeds, so they are descriptive anchors, not equal-budget comparisons. Residual results do not decide standalone PPO capability.

During training B executes a residual on only 1.04–1.43% of completed-episode steps; D on 0.64–0.95%. D's mean added bonus is approximately 0.0000075–0.0000097. Sparse execution and a small reward signal are plausible obstacles, not a demonstrated causal explanation. This negative pilot result applies to this fixed design and budget, not every possible gate-aware objective. Two seeds do not establish statistical significance, convergence or safety.

## Development and reserved separation

Development uses base 6100000 and the explicit IDs in [reserved_split.json](reserved_split.json). An allocation audit discovered that the originally proposed, unused reserved base 8100000 would overlap 36 development IDs under future seed 2 versus pilot seed 202. Before any reserved evaluation, the separate manifest superseded it with base **91000000**, listing 180 future IDs disjoint from all 72 development IDs. The original frozen protocol is preserved as evidence; use the corrected manifest for any future reserved work. No controller or observed development result changed.

## Reproduction

From the repository root, use the pinned research environment described in the parent research documentation. The recorded execution used `/workspace/lans-setup/venv/bin/python` (NumPy 1.23.5, SciPy 1.10.1, Torch 2.0.0+cpu, SB3 2.0.0, Gymnasium 0.28.1, Numba 0.57.1).

```bash
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-v4-numba MPLCONFIGDIR=/tmp/lans-mpl
"$LANS_PYTHON" integrations/webots/research/revision4/test_contracts.py -v
"$LANS_PYTHON" integrations/webots/research/revision4/run_pilots.py --output "$PWD/integrations/webots/results/revision4-local"
"$LANS_PYTHON" integrations/webots/research/revision4/report4.py
```

The runner requires a new output directory and can conditionally extend an eligible model from its saved 100k checkpoint to 300k. It never launches 5×1M. The report command audits the committed canonical `revision4-pilots` directory; it does not ingest `revision4-local`. Checkpoints, optimizer/normalization state, source snapshots, training monitors, decision JSON, all episode rows and representative compressed traces are retained. Five contract tests cover baseline parity, actual gate parity, zero bonus, counterfactual symmetry/nonmutation and randomized-domain bounds/reproducibility.

## Relation to controller review c9a0481

The [controller review](https://github.com/rizwanalihasalivi/LANS/blob/c9a04819f21d1b6cb5e84eef315dbca24be7f288/docs/research/controller-review/README.md) was read after these pilots completed. Its ten diagnostic episodes are a different grid and must not be combined with this table. They provide evidence against blindly increasing PPO authority, not a general proof that every candidate is harmful.

| Review item | Revision4 coverage / remaining gap |
|---|---|
| Legacy pipeline quarantine | Only the isolated research plant is used here. Legacy comparative claims are excluded; root code was not repaired or modified. |
| Execution mismatch R1 | B/D execute the actual frozen gate, weighting, recovery and fallback each tick. Training is synchronous; gate state/history and service-age information are not actor observations. Therefore deployment matching is partial, not complete. |
| Predictor audit R4 | Still missing: paired cloned-state predicted versus realized cost deltas, false accepts/rejects and estimator/actuator attribution. The privileged training reward is not this audit. |
| Relative objective R5 | C/D test one explicitly defined counterfactual bonus. Its small magnitude and sparse D execution are recorded; no scale tuning followed the results. |
| Nonlearned controls R7 | Still missing from the full development grid. Both constant signs, zero candidate and a predeclared simple model-based correction should be compared under the same gate before attributing gains to learning. |
| Distribution R3 | D includes friction, stiffness, sensor noise/delay variation, but bundles these with reward/gate changes and course screening. It cannot isolate randomization's contribution. |
| Information mismatch R9 | Same nine observations retained; no gate history or hidden parameters. Existing LQR scheduled-speed and map/actuator idealizations remain. |
| Severe delay R10 | Exact LQR fallback is preserved; equality is not counted as learned improvement. |

The next justified research step is diagnostic attribution on development states, not another training-budget increase. Freeze audit horizons, continuation semantics, candidate baselines, sampling and acceptance definitions before execution. Distinguish the gate's nominal predictor from privileged realized-plant counterfactuals; never feed hidden test parameters into the deployed gate. Any later training change needs a new protocol and independent reserved evaluation. No such additional campaign was run in this revision.
