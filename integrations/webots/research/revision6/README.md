# Correction-quality pilot

This user-authorized experiment tests whether execution-aware training improves the quality of learned residual corrections, preserving the strong LQR and frozen gate. It is a controlled 600k-transition pilot, not a full campaign or automatic claim of superiority.

- Training freeze: `1201f8d`, before any policy training.
- Evaluation/MPC freeze: `55b8ff8`, before development evaluation.
- Report/decision implementation freeze: `8e21556`, before evaluation results.
- [Protocol](protocol.json): exact seeds, budgets, reward, distributions, comparisons and stop rules.
- [Results](../../results/revision6-correction/report.md): generated only after all648 paired episodes finish.

## Controlled change

Both arms train from scratch at seeds301/402/503 for100k steps each, with identical PPO settings,20-feature observations, ±0.08-rad proposal range and nominal random-sine distribution. Both use the same executed-command reward, including the existing privileged relative-cost term. Training is synchronous at zero service delay in both arms to isolate execution rather than also change delay distribution.

`direct` applies the proposed residual directly during training. `execution` applies the unchanged performance gate during training. The visible execution history differs as a consequence of those actions; this is part of the treatment. Both models deploy under the same frozen gate at evaluation. Older policies are not warm-started or relabeled.

The grid covers three model/noise seeds, three speeds, two known paths, and six scenarios. Methods are LQR, nominal constrained MPC, constant positive/negative candidates under the gate, and both learned arms. All use the same nonlinear plant, estimator, observed-speed channel and physical actuator constraints. PPO and MPC receive the same three curvature-preview samples; LQR retains its existing local-curvature design. MPC uses no hidden friction/stiffness or future noise. Its own local solver is not given the artificial service delay applied to learned/constant workers; all wall times are disclosed separately.

The MPC is a new explicitly specified nominal reference:20×50ms prediction,10ms replanning, linear bicycle plus actuator, common LQR Q/R, Riccati terminal cost, command/actuator/rate constraints. Its OSQP status and any fallback-to-LQR are counted. It is not a claim to have found the best possible MPC or a nonlinear MPC optimum. Model mismatch and repeated development geometry limit generality.

## Reproduce

Use the pinned research Python3.10 runtime; additionally install `requirements-mpc.txt` (OSQP0.6.3). In the prepared cloud machine the tested executable is `/workspace/lans-venv/bin/python`.

```bash
cd /workspace/LANS
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/workspace/lans-v6-numba
export MPLCONFIGDIR=/workspace/lans-setup/matplotlib
python integrations/webots/research/revision6/test_training.py -v
python integrations/webots/research/revision6/test_evaluation.py -v
# Choose new directories; never overwrite committed models/results.
python integrations/webots/research/revision6/run_training.py --output /tmp/lans-v6/training
python integrations/webots/research/revision6/run_evaluation.py \
  --training /tmp/lans-v6/training --output /tmp/lans-v6/evaluation
python integrations/webots/research/revision6/report.py --run /tmp/lans-v6
```

Training uses two concurrent CPU processes, each one Torch/BLAS thread; evaluation uses three independent seed shards. The smoke/parity tests and MPC equilibrium/constraint tests are bounded prerequisites. Training logs retain Monitor episodes, optimization/rollout diagnostics, normalization, fixed final models and source snapshots. Evaluation retains every episode, solver fallback counts and representative first-seed25m/s DLC traces. Failed tails are scored at2.5m; uncertainty is across three paired seed means, not correlated time samples.

No policy is selected by its final development score. The predeclared progress check requires ≥1% execution-versus-direct improvement plus seed/region/survival conditions; learning-specific benefit additionally requires ≥1% over LQR and both constants. MPC advantage is a separate check. Even if a screen passes, this task stops after the pilot. No reserved test, native Webots campaign, larger-budget extension, gate retuning or second search is automatically launched.
