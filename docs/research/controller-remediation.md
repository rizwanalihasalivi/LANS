# Controller review remediation

This branch addresses the review at `c9a04819f21d1b6cb5e84eef315dbca24be7f288`. The user explicitly expanded the task from isolated integration changes to all review issues, including root-code defects. Work is isolated on `fix/controller-review`; the main worktree, specification, `experiments/phase1/`, shared Webots installation and historical research models/results are unchanged.

A code correction cannot establish a learned performance advantage or a real-world safety guarantee. The table distinguishes repaired contracts, new evidence, intentional constraints and remaining scientific limits.

## Legacy defects L1–L8

| ID | Remediation | Verification |
|---|---|---|
| L1 | Root plant integrates world x/y/heading/body lateral velocity/yaw rate with RK4; errors are derived from independent reference geometry. Reference values cannot move the vehicle. `PathTrackingEnv` accepts a full radian command and adds no LQR. | Zero steering on a curved path keeps y=0 and eventually leaves the tracking envelope, instead of falsely following the reference. |
| L2 | `ResidualPathEnv` alone computes scheduled LQR + normalized action ×0.08 rad, clips once and passes the full command to the physical parent. Logged total equals applied command. | Paired full-command and residual environments have identical physical states for the same applied command over several actions. |
| L3 | Invalid legacy comparison, data-collection and tuning entry points are quarantined with actionable migration errors; exact earlier implementations remain in Git. `tools/controller_review/compare.py` runs paired controllers through one full-command plant, respects termination and fills failed tails explicitly. No hard-coded reference score. | 36 corrected demonstration episodes, paired keys and failure denominators checked. These are deterministic repeated fixtures, not 36 independent statistical trials. |
| L4 | Learned root controller requires a versioned bundle with policy, normalization, role, action scale, observation contract and SHA256 hashes. No silent missing-policy fallback. Four real path previews are supplied before inference; normalization is restored and frozen. | A new 1000-step smoke checkpoint loads with exact normalized-prediction parity. Missing bundle fails. Old root checkpoints are incompatible and require retraining; they are not relabeled as corrected models. |
| L5 | `target_speed` aliases the actual `vx`; physical reference coordinates are stored against distance. LQR gains are calculated from speed/parameters with Riccati control and turning equilibrium. Environment/controller previews and observation speed agree. | Speed15/25 gain variation, reset-seed/path reproducibility and environment/controller observation parity checks. |
| L6 | Root training is explicitly synchronous and no longer calls arithmetic duration “action latency.” Corrected evaluator advances physics during unavailable inference, holds timestamped packets and falls back at age≥50ms. Actual inference benchmarking is a separate wall-time measurement without synthetic fallback. | 20/100ms simulation tests and exact100ms fallback; execution-interface tests verify pending-packet identity/age. Real-process worker remains the existing separate concurrency mechanism. |
| L7 | Old curriculum entry points no longer assign an ineffective attribute. Corrected trainer uses an explicit budget and constant initial LR; `set_learning_rate` updates both SB3 schedule and optimizer when needed. | Schedule and optimizer LR equality tested. No historical curriculum/model is claimed corrected retroactively. |
| L8 | Reference sampling uses Gym's seeded RNG. Exact zero-order-hold helper uses SciPy `expm` with a zero lower block. | Same-seed paths/observations match; analytic integrator discretization matches A_d=I, B_d=dt×B. |

The root demonstration is a linear-tire bicycle plant without the research surrogate's nonlinear tire/actuator model. It is suitable for contract checks, not a replacement source for paper claims. Observation/action contracts changed intentionally; older models must be retrained under corrected semantics. No old checkpoint was overwritten.

## Research findings R1–R10

| ID | Action and evidence | Remaining limit |
|---|---|---|
| R1 | New revision5 `Execution` is shared by the corrected training environment and its execution tests: the exact frozen gate, weight ramp, persistence, recovery and fallback transform commands before physics/reward. The20-feature observation includes gate state, held packet, pending request, ages, last command and service delay. | This is a surrogate interface repair validated by smoke training. It is not a newly qualified native policy. |
| R2 | Explicitly retain ±0.08-rad candidate and≤0.5 blend authority, including physical exploration std≈0.010827rad at logstd−2. No weight increase is presented as a fix. | Deliberate bounded-residual architecture cannot support PPO-dominance claims. |
| R3 | Optional domain randomization records realized friction/stiffness/noise/sensor-delay samples. Inference service delay is separately sampled from0/10/20/100ms in the execution interface. Nominal training remains separately selectable. | This distribution does not cover every real vehicle, mass, actuator or disturbance; no adaptation claim. |
| R4 | Frozen predictor audit compares predicted and nonlinear realized paired cost differences, records false accepts/rejects and separately reports safety/recovery rejections. True-state predictor deltas help expose estimation versus model mismatch. A separate conservative nonlinear model-bank predictor is implemented and evaluated without hidden scenario parameters. | Neither predictor is an oracle or safety certificate. See separate model-bank results and promotion screen; historical gate stays frozen. |
| R5 | LQR-relative reward is computed for the command actually executed. Tracking, effort, change, survival, relative reward and both cost branches are logged. PPO advantages, KL, entropy, clipping and critic fit are saved. | Counterfactual reward remains a training-only simulated objective, not guaranteed realized long-term improvement. No post-result scale tuning. |
| R6 | Units and exploration are explicit; old-policy mappings remain isolated. New interfaces reject incompatible shape/role contracts. | No untested “larger network fixes exploration” claim; exploration search would require a new controlled protocol. |
| R7 | Zero, +0.08, −0.08 and predeclared bounded linear feedback candidates run under the same gate on all72 paired cells alongside legacy and100k PPO. Every sign/result retained. | These controls establish attribution limits; they do not prove all possible nonlearned controllers inferior or superior. |
| R8 | Historical checkpoints/data remain immutable. Diagnostics reuse declared development noise, not final reserved data. The execution trainer is smoke-only; no full-budget launch. | Two reused development seeds cannot establish generalization, convergence or significance. |
| R9 | In the new execution environment, actor, LQR and gate all receive the same measured-speed channel. Existing gain schedule is interpolated; packet/gate history is observable. Ground-truth dynamics parameters enter only the plant/reward diagnostic. | The map position, actuator feedback and estimator model remain declared simulation assumptions. Old historical evaluations retain their disclosed scheduled-speed asymmetry. |
| R10 | Stale packets cause exact LQR fallback; equality is not counted as an AI performance win. | This proves the simulated contract, not real-vehicle safety under arbitrary failures. |

During delayed training, actions sampled while the single worker is busy are not submitted. A held/pending action is part of the observable control state, so delayed rewards propagate through that state; logs identify the originating packet. This does not pretend that an older packet is the newly sampled action. Unobserved plant/sensor state still makes the system partially observable;20 features do not establish a fully observed MDP.

## New diagnostic results

[Complete paired report](../../integrations/webots/results/revision5-audit/report.md) and [raw predictor audit](../../integrations/webots/results/revision5-audit/predictor-audit.csv): **504 episodes**, all survived; **15,648 sampled state/candidate rows**. All72 LQR cells exactly reproduce revision4 reference values. Severe-delay fallback is exact for every candidate.

| Method | Mean RMSE (m) | Change vs LQR |
|---|---:|---:|
| LQR / zero candidate | 0.084253 | 0% |
| Legacy PPO + gate | 0.082702 | −1.841% |
| 100k PPO + gate | 0.083821 | −0.514% |
| Constant +0.08 + gate | 0.083757 | −0.589% |
| Constant −0.08 + gate | 0.083614 | −0.759% |
| Linear correction + gate | 0.084253 | approximately0% |

The legacy learned reference outperforms the tested nonlearned controls in the aggregate; the100k policy does not. Different training budgets and seeds prevent an equal-budget learning claim. Nominal predictor false accepts are38/664 accepted sampled legacy actions and77/451 for100k PPO. Cost false rejects are98/1893 and117/2112 respectively under the predefined>1% realized-effect threshold. These are correlated shadow decisions on LQR trajectories, not failure probabilities or policy-specific deployed safety rates.

An initial diagnostic entry point omitted `configure_lqr` and ran the original aggressive gains. That run is explicitly invalid and retained under `revision5-audit-invalid-config`; it is excluded from conclusions. The corrected pre-run freeze `b86cfa8` adds exact historical LQR parity requirements. The nonlinear-bank experiment has its own freeze `d29089a` and [separate report](../../integrations/webots/results/revision5-robust/report.md).

## Reproduction

Use the pinned Python environment from cloud setup (recorded executable `/workspace/lans-setup/venv/bin/python`). From repository root:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-v5-numba MPLCONFIGDIR=/tmp/lans-mpl
python tests/test_controller_remediation.py -v
python integrations/webots/research/revision5/test_execution.py -v
python integrations/webots/research/revision5/test_robust_gate.py -v
python tools/controller_review/train.py --steps 1000 --output /tmp/lans-root-bundle
python tools/controller_review/compare.py --bundle /tmp/lans-root-bundle --output /tmp/lans-root-comparison
python tools/controller_review/benchmark.py --bundle /tmp/lans-root-bundle --output /tmp/lans-root-timing.json
python integrations/webots/research/revision5/smoke_train.py --randomize --output /tmp/lans-execution-smoke
python integrations/webots/research/revision5/audit.py --output /tmp/lans-predictor-audit
python integrations/webots/research/revision5/report.py --input /tmp/lans-predictor-audit
python integrations/webots/research/revision5/robust_run.py --output /tmp/lans-model-bank
```

Each output directory must be new. `robust_run.py` compares against the committed canonical revision5 reference grid. Artifact verification commands `tools/controller_review/verify.py` and the report generator audit committed canonical evidence. Smoke models are not replacement production/research policies. No1M/5M training, final reserved evaluation or new native Webots campaign was run.

## Validation record

[Machine-readable tests](../../integrations/webots/results/controller-remediation/test-results.json) record36 passing unit/contract checks across corrected root, execution interface, nonlinear bank, existing research, frozen gate, action mapping and native adapter. The existing cloud smoke also passes with its repository path made worktree-relative (two128-step training/save/load checks). [Artifact audit](../../integrations/webots/results/controller-remediation/verification.json) verifies both1000-step smoke checkpoints, restored normalization/prediction parity,36/36 root demonstration survival,1000 execution transitions, optimizer diagnostic presence and exact severe-delay fallback.

Actual synchronous inference timing is recorded in [inference.json](../../integrations/webots/results/controller-remediation/inference.json). It measures the new small smoke model on this shared CPU environment and includes normalization; it is not a universal rate, asynchronous deadline guarantee or performance measurement of the historical research policies.

## Nonlinear-bank outcome

The separate frozen model-bank comparison completed **144/144 surviving episodes**, with exact severe-delay fallback. It did **not** meet the predeclared promotion rule for either legacy or100k PPO: stress means did not improve in both seeds. Legacy nominal RMSE changes0.061223→0.061504m and tire mismatch0.172033→0.172332m; low-friction changes0.080137→0.080133m. Results are mixed, so the experimental bank is **not promoted** and no further predictor tuning follows this grid. [Independent verification](../../integrations/webots/results/revision5-robust/verification.json).

The review's concrete implementation defects and missing diagnostics have been addressed. The research goal of a demonstrably better predictor/policy remains unproven; it cannot honestly be marked fixed by a code change. No new policy should be deployed as a superior controller on the strength of these smoke runs or mixed development comparisons.
