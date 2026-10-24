# Pilot-selected residual training with matched steering units

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

`selection.json` freezes the complete ranking, selected configuration, source hashes, all pilot model hashes and development data hash. Only the selected configuration is then trained **from scratch**, five seeds 0–4, one million steps each. No pilot is warm-started or promoted to a longer budget. The final fixed checkpoints are compared on fresh noise base **4910000**, not the earlier unused 2910000 plan. There is no post-test tuning.

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
bash integrations/webots/research/revision3/run-training.sh \
  "$PWD/integrations/webots/results/range-training-local" \
  "$PWD/integrations/webots/results/range-pilots-local/selection.json"
"$LANS_PYTHON" integrations/webots/research/revision3/evaluate.py \
  --training "$PWD/integrations/webots/results/range-training-local" \
  --selection "$PWD/integrations/webots/results/range-pilots-local/selection.json" \
  --output "$PWD/integrations/webots/results/range-test-local"
"$LANS_PYTHON" integrations/webots/research/revision3/native_smoke.py \
  --training "$PWD/integrations/webots/results/range-training-local" \
  --output "$PWD/integrations/webots/results/range-native-local"

# Verify/report canonical committed evidence (fixed canonical paths):
"$LANS_PYTHON" integrations/webots/research/revision3/report.py
```

The original execution used canonical directories `revision3-pilots`, `revision3-training`, `revision3-test` and `revision3-native-smoke`. Pilot/evaluation orchestration used `/workspace/lans-setup/venv/bin/python`; full training and Webots controllers use the existing pinned private runtime. Four training processes run at most, with one Torch/BLAS thread each. Source snapshots, progress, episode Monitor logs, completed models, normalization artifacts and hashes are retained.

## Evaluation and interpretation

The reserved grid has 900 episodes: five full-training seeds × three speeds × two known paths × six scenarios × five methods:

- LQR.
- Legacy residual policy, original ×0.5 decoder, frozen gate clipping.
- Legacy policy simply rescaled to ×0.08, same gate.
- Selected retrained policy at ×0.08, same gate (primary new method).
- Selected retrained policy at ×0.08 without performance gating, retaining the existing age decay.

The primary comparison is retrained gated versus legacy gated. LQR and simple rescaling are predefined secondary references. Raw inference statistics record requested residual magnitude, fraction beyond the gate cap and normalized saturation. All methods use matched noise streams, and all cases remain in the report. Scores penalize unexecuted failed tails at 2.5 m; uncertainty is across five paired seed means, not correlated time samples. Descriptive t intervals are not adjusted for multiple comparisons.

Five native 20 m/s runs, one per newly trained policy seed, verify actual worker decoding and controller execution. Received packet logs retain legacy encoded values and mapped residual radians. These runs are **unpaired interface checks**, not a full native performance comparison. Earlier native improvement results belong to the earlier policies and cannot be transferred to these new weights without new paired tests.

See the [pilot ranking](../../results/revision3-pilots/report.md) and [reserved results](../../results/revision3-test/report.md). The range fix alone does not establish better control, convergence, stability, real-vehicle safety or broad generalization.
