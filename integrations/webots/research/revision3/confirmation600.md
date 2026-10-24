# Baseline 600k confirmation

This stage follows the user's request to extend only the two baseline pilots before considering a five-million-step campaign. The exact `baseline-101` and `baseline-202` checkpoints from `results/revision3-extended` are continued from300k to600k total steps. The larger network is not trained. Gate, residual range, reward, network and PPO settings are unchanged.

The protocol was committed as `c9978e7dd9b372a6c6e8068968cf1183387ede8e` before continuation. Each job restores PPO weights, Adam and VecNormalize statistics, then executes300k additional steps with `reset_num_timesteps=False`. Assertions verify optimizer counters15000→30000, normalization counts300k→600k and actual saved model counters. Environments reset with SB3's effective `model.seed+i` behavior, matching the previous continuation; this is not an uninterrupted600k trajectory. Saved initial hashes and resume audits make that distinction reviewable.

The same development cells are used: two seeds × three speeds × two paths × six regions. The600k model plus LQR, old gated and old-rescaled gated references produce288 episodes. All216 rerun reference cells must exactly reproduce the prior errors and survival. Historical100k and300k baseline rows supply the earlier curve points. No model/threshold choice uses the reserved noise base4910000, and no native simulator run is requested in this stage.

## Reproduce

From the checkout root with the existing pinned environment:

```bash
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR="$PWD/integrations/webots/.runtime/numba"
export MPLCONFIGDIR="$PWD/integrations/webots/.runtime/mpl"
"$LANS_PYTHON" integrations/webots/research/revision3/confirm600.py \
  --initial "$PWD/integrations/webots/results/revision3-extended" \
  --output "$PWD/integrations/webots/results/confirmation600-local"

# Audit/report canonical committed results (fixed canonical paths):
"$LANS_PYTHON" integrations/webots/research/revision3/report600.py
```

The actual run used `/workspace/lans-setup/venv/bin/python` and canonical output `results/revision3-600k`. Output directories must be new. Two subprocesses run concurrently, each with one Torch/BLAS thread. The runner records complete source snapshots, progress, training Monitor logs, normalization/model artifacts, resume metadata, per-condition evaluation rows and representative traces. All old checkpoints/evidence are retained.

## Decision rule and limits

The frozen operational progress check requires at least1% mean RMSE improvement over both the300k baseline and old-rescaled reference, improvement for both seed means against300k, improvement in at least4/5 active regions, no active region >1% worse than300k, nominal within2% of LQR and no regional survival decrease. The legacy-gated gap is reported separately as an aspirational reference. These are practical budget-review criteria, not statistical significance or proof of convergence.

All regional values and seed means are reported even if this rule fails. The task ends at the600k checkpoint: five-seed full training remains unapproved. No additional configuration search or reserved evaluation is performed. A small or flat effect would weaken the case for that expense; it would not prove that no possible future training could help.

Only two training seeds and repeatedly used development paths/noise are tested. The old reference policies have1M steps and different training seeds0/1. They are descriptive anchors, not an equal-budget causal comparison. The learning curve consists of three measured endpoints100k/300k/600k; lines between them are visual guides, not additional observations.

[Results](../../results/revision3-600k/report.md) · [Audited decision](../../results/revision3-600k/decision.json) · [Learning-curve figure](../../results/revision3-600k/learning-curve.png)
