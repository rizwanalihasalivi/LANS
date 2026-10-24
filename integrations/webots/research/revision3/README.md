# Staged residual pilots with matched steering units

**Latest authorized stage:** baseline-only300k→600k confirmation; see [the continuation guide](confirmation600.md). The historical300k comparison below remains unchanged. Five-seed full training is still unapproved. No completed new1M policies, final reserved evaluation or new-policy native smoke results exist yet. The later full-training/evaluation code is prepared, not evidence of execution.

The user identified an action-range mismatch: earlier residual policies trained with normalized action ×0.50 rad, while the frozen performance gate clips candidate residuals to ±0.08 rad. This revision trains candidates at normalized action ×0.08 rad and uses an explicit decoder in both surrogate and native inference. Existing gate, LQR, policies and held-out results remain unchanged.

## User-requested pilot-first workflow

An initial direct five-seed run was interrupted when the user requested small pilot comparisons before full training. Four jobs had reached their last recorded 530k-step progress points; no completed checkpoints or reserved evaluation rows existed. Partial files are preserved locally under `.runtime/revision3-interrupted-before-pilots/`, with a compact committed `interrupted-run.json` record. They are not used in selection or counted as completed final training. The earlier 1,000-step interface smoke remains historical evidence from before the pilot workflow change.

The replacement protocol was frozen in commit `bbb010cfcef75a91e535c408c5b5ad4e76c13841`, before any pilot scores. `pilots.json` defines four candidates, each trained from scratch for 100,000 steps at seeds 101 and 202:

| Candidate | Network | Initial log standard deviation | Tracking reward scales (lateral / heading) |
|---|---|---:|---|
| baseline | [64,64] | −2 | 0.5 m / 0.1 rad |
| low_exploration | [64,64] | −3 | 0.5 m / 0.1 rad |
| tracking_reward | [64,64] | −2 | 0.35 m / 0.08 rad |
| larger_network | [128,128] | −2 | 0.5 m / 0.1 rad |

All other training settings, candidate range and gate rules stay fixed. The tracking reward retains the positive-survival form and existing steering/change penalties. Pilot selection uses 360 development episodes: 72 per candidate plus 72 paired LQR episodes, covering three speeds, two known paths and six scenarios. Noise base 4100000 is development-only. Eligible candidates must preserve aggregate survival and remain within 2% of LQR's nominal RMSE; the lowest mean penalized RMSE wins. If none qualifies, the rule explicitly marks the best available choice as unqualified rather than hiding failure.

`selection.json` freezes the complete ranking, selected configuration, source hashes, all pilot model hashes and development data hash. The planned next stage trains the user-approved configuration **from scratch**, five seeds 0–4, one million steps each. It is paused pending the extended-pilot checkpoint and user decision. No pilot is warm-started or promoted to a longer budget. Future final fixed checkpoints will be compared on fresh noise base **4910000**, not the earlier unused 2910000 plan. There is no post-test tuning.

Short-run ranking is noisy: two pilot seeds and 100k steps cannot guarantee which configuration would win at one million steps. The selected architecture/reward is a development choice, not a proof of global optimality.

## Action semantics

The existing environment and inference interfaces decode normalized actions with a historical ×0.5 factor. `mapping.legacy_units` supplies a ×0.16 conversion before that boundary so the physical candidate is ×0.08. This reuses the original dynamics/reward implementation without editing old experiment code. It clips normalized inputs and rejects nonfinite actions. Candidate residual is then added to LQR, complete command is bounded to ±0.5 rad, and the unchanged actuator applies its lag/rate limits.

Surrogate inference uses the same conversion. The native worker historically emits normalized action ×0.5; `map_worker_packet` converts that encoded output **once** to ×0.08 before the frozen gate. Checkpoint metadata declares `residual_scale_rad: 0.08` and the native adapter verifies profile, step count and model hash. **Do not load these weights directly through an unmodified ×0.5-rad decoder.** Keep the model and its metadata together.

Matching candidate range does not mean full deployment-aware training. Training still applies the residual directly, while deployment can gate/reject it and multiply by a weight ≤0.5. The effective correction is therefore smaller and time-dependent. No gate-in-the-loop reward attribution, asynchronous training curriculum or new mismatch training distribution has been introduced. Reducing the action scale also reduces physical exploration variance for the same normalized policy standard deviation.

## Reproduce

Use the existing pinned private environment. From the checkout root:

```bash
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR="$PWD/integrations/webots/.runtime/numba"
export MPLCONFIGDIR="$PWD/integrations/webots/.runtime/mpl"
"$LANS_PYTHON" integrations/webots/research/revision3/test_range.py -v

# Choose new output directories; existing evidence is never overwritten.
"$LANS_PYTHON" integrations/webots/research/revision3/pilot_search.py \
  --output "$PWD/integrations/webots/results/range-pilots-local"
"$LANS_PYTHON" integrations/webots/research/revision3/extended_search.py \
  --initial "$PWD/integrations/webots/results/range-pilots-local" \
  --output "$PWD/integrations/webots/results/range-extended-local"

# Audit canonical committed extended checkpoints (fixed canonical paths):
"$LANS_PYTHON" integrations/webots/research/revision3/audit_extension.py
# Full training/evaluation stays paused until the user chooses the configuration.
```

Completed pilot stages use `revision3-pilots` and `revision3-extended`. Interrupted `revision3-training` and empty `revision3-test` directories were archived under `.runtime`; no `revision3-native-smoke` was run. Pilot/evaluation orchestration used `/workspace/lans-setup/venv/bin/python`; full training and Webots controllers use the existing pinned private runtime. Four training processes run at most, with one Torch/BLAS thread each. Source snapshots, progress, episode Monitor logs, completed models, normalization artifacts and hashes are retained.

## Evaluation and interpretation

The planned, unrun reserved grid has900 episodes: five full-training seeds × three speeds × two known paths × six scenarios × five methods:

- LQR.
- Legacy residual policy, original ×0.5 decoder, frozen gate clipping.
- Legacy policy simply rescaled to ×0.08, same gate.
- Selected retrained policy at ×0.08, same gate (primary new method).
- Selected retrained policy at ×0.08 without performance gating, retaining the existing age decay.

The primary comparison is retrained gated versus legacy gated. LQR and simple rescaling are predefined secondary references. Raw inference statistics record requested residual magnitude, fraction beyond the gate cap and normalized saturation. All methods use matched noise streams, and all cases remain in the report. Scores penalize unexecuted failed tails at 2.5 m; uncertainty is across five paired seed means, not correlated time samples. Descriptive t intervals are not adjusted for multiple comparisons.

Five native20m/s interface runs are prepared for future full-trained policies; they have not run. Received packet logs retain legacy encoded values and mapped residual radians. These runs are **unpaired interface checks**, not a full native performance comparison. Earlier native improvement results belong to the earlier policies and cannot be transferred to these new weights without new paired tests.

See the [100k pilot ranking](../../results/revision3-pilots/report.md), [300k extended comparison](../../results/revision3-extended/report.md) and [continuation audit](../../results/revision3-extended/continuation-audit.json). The range fix alone does not establish better control, convergence, stability, real-vehicle safety or broad generalization.

## Close top-two extension and user checkpoint

The initial gap between baseline and larger network was only0.31%. The user required more evidence before full training, so that preliminary full run was also stopped with no completed models or reserved test rows. The last recorded partial counters were320k/310k/320k/320k; `interrupted-selected-run.json` records them, and the files remain locally archived under `.runtime/revision3-interrupted-before-extended-pilots/`.

The two existing100k pilot checkpoints at each of seeds101/202 were continued for **200k additional steps**, reaching **300k total**, with policy, Adam optimizer and VecNormalize reward statistics restored. `extension.json` and the continuation/evaluation code were frozen in commit `8d30230120ad531a5bc073c83d8c9590123d3ddc` before results. The extension adds800k steps, for1.6M cumulative pilot steps across both stages. All360 extended development cells include LQR, old gated policy, old simply rescaled gated policy, baseline and larger network.

An independent audit verified nonzero optimizer counters in the initial checkpoints, larger counters afterward, exactly200k additional normalization samples and the saved100k→300k step counts. **Seeding caveat:** SB3 `PPO.load` overrides constructor seed defaults with `model.seed+i`; the intended fresh constructor offset in the frozen protocol was not effective. Environments restarted from those seeds, while learned parameters and optimizer/normalization continued. Both configurations received the same treatment. This is not an uninterrupted300k trajectory; the audit records the discrepancy rather than rewriting frozen provenance or rerunning to chase results.

The predeclared operational clear-winner rule requires ≥1% mean improvement, better means in both seeds, improvement in at least4/5 active regions with no region >1% worse, nominal within2% of LQR and no regional survival loss. This is a spending criterion, not statistical significance. The user's latest instruction adds a simplicity preference when the gap remains small and explicitly asks to review the300k numbers before authorizing full training. Therefore any numeric `full_training_authorized` field in the original decision artifact denotes only the earlier automatic criterion; **no full training will start before that user decision**. No further configuration search is performed in this stage.

Old comparison policies are1M-step models at seeds0/1 paired with pilot noise for seeds101/202. Their different budgets/model seeds make them descriptive anchors, not an equal-budget proof of retraining benefit. Reserved noise4910000 remains unused.

## 300k checkpoint outcome

All360 extended development episodes survived. Baseline mean RMSE is0.084229m versus0.084317m for the larger network: only0.104% apart, with split seed wins. Neither is a clear performance winner. Baseline is the simplicity recommendation under the user's latest tie-break, not a demonstrated superior policy. The old merely rescaled reference is0.084201m; a distinct benefit from new training is not yet established at this budget. Sensor-stress error remains slightly worse than LQR.

Full training is paused for the user to review these numbers. The full-training launcher now requires a separate `user-selection.json` with an explicitly recorded user-approved selection; numerical pilot eligibility alone cannot start it. Final reserved tests and new-policy native checks have not run.
