# Tire-mismatch attribution diagnostic

**Corrected replay is complete:** [current results](../../results/full-project-audit/revision11-corrected/report.md) retain 8/8 survival. Tire/student shadow decisions now show 11 lateral-harm approvals out of 32 accepted and 26 helpful cost rejections out of 388. The archived figures below are superseded.

**Timestamp correction:** the archived student behavior below re-submitted held proposals on intermediate ticks and refreshed their observation timestamps. Corrected drivers submit only at actual50ms policy queries, retaining original packet age between queries. The independent shadow candidates remain fresh every tick by design; this is a separate hypothetical shadow process, not the student submission stream. Preserve the old output and rerun into a new directory before relying on revised counts.

[Full report](../../results/revision11-attribution/report.md) · [Raw branches](../../results/revision11-attribution/branches.csv) · [Verification](../../results/revision11-attribution/verification.json).

Protocol/executable frozen at `bc2517c`, before execution. Eight common behavior trajectories: two fresh development noise repetitions, nominal/tire-mismatch, LQR/student,25m/s DLC220. Student proposal query cadence50ms matches revision10; no current model/gate is modified. No final-test data, training or promotion is used.

## Findings

All8 trajectories survive;11,238 branch rows cover5,280 sampled state/candidate/horizon groups. No counterfactual branch fails. Three horizons200/400/1000ms are reported in raw data. The200ms tables compare the frozen nominal gate's prediction with paired nonlinear interventions; lateral and combined tracking/yaw/effort objectives are kept distinct.

On tire-mismatch **student behavior** states:24 shadow accepted decisions include9 with >1% lateral harm and8 with >1% combined-cost harm. Among397 cost rejections,25 have at least one ramp-allowed intervention with >1% lateral benefit;9 additional helpful cases are withheld by persistence/recovery rules. These are correlated shadow decisions along common trajectories, not actual deployed-policy failure probabilities. Counts are not comparable as independent significance tests.

Across996 tire-mismatch available-proposal comparisons,27 have opposite meaningful signs for combined versus lateral cost at200ms.68 proposals helpful for lateral error at200ms are harmful at1s;37 flip in the other direction. Nominal states also exhibit predictor/objective disagreements, so stiffness mismatch alone is not established as the cause.

The current student mean on this new narrow tire slice is0.197544m versus LQR0.196380m; nominal student0.075475m versus LQR0.076527m. This does not replace its broader frozen evaluation.

## What this establishes

There are concrete missed opportunities, harmful approvals and horizon/objective disagreements worth testing. It does not establish which modification will improve full closed-loop episodes, nor unlock5%. Counterfactual commands are held50ms, then all branches use estimated-state LQR; this is not future student/teacher replanning. Hidden stiffness and actual future noise enter the offline diagnostic plant/measurements only, never the deployed gate or student.

The realized combined metric uses the gate's functional weights but evolving physical curvature and true scheduled-speed yaw reference. Predictor discrepancy thus includes dynamics, geometry, estimator and input-reference effects. A causal attribution to one component needs a further controlled ablation.

The justified next protocol, if pursued, is a matched predictor/objective ablation: retain the current gate as reference, change only predictor geometry/dynamics or only decision objective, and compare whole episodes with nominal/survival/stale fallback preserved. Do not increase authority or launch PPO/full training based on shadow minima. No additional experiment or post-result tuning is included here.

## Reproduce

Use the pinned research environment and a new output directory:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-v11-numba MPLCONFIGDIR=/tmp/lans-mpl
python integrations/webots/research/revision11/test_attribution.py -v
python integrations/webots/research/revision11/run.py --output /tmp/lans-tire-attribution
python integrations/webots/research/revision11/report.py --run /tmp/lans-tire-attribution
```

Two focused contract checks pass: branch nonmutation/Python parity/future-window isolation and zero-state identical-control cost. The report verifies all eight behavior keys, branch row counts, exactly one executed action per sampled group and zero executed benefit when the gate withholds. Source snapshots, logs, raw trajectory and branch summaries are retained.
