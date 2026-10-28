# PPO performance audit and resumable experiment v12

The20% target is a research objective, not a result that can be guaranteed by debugging. This audit covers the active training/normalization/action-credit, sensing, packet lifecycle, supervisor/recovery, compensation, physical reward/plant, export, runtime and selection chain. The repository-wide Python inventory supplies syntax/hash coverage; it is not a claim that every historical source line is semantically verified.

## Confirmed defects and changes

1. Response-delay compensation still used10ms semi-implicit Euler while the supervisor had moved to1ms RK4. Version12 uses the same nominal dynamics and held10ms LQR control with1ms RK4 in the input forecast and causal planner. Across24 fixed independently integrated DOP853 cases, maximum state error changes from 0.0037186141 to 9.1515286e-08. This corrects numerical inconsistency; it does not identify the unknown nonlinear plant or prove tracking improvement.
2. The previous runner refused partial training folders. The new runner saves atomic, hashed update-boundary checkpoints including actor/critic/Adam, full environment and worker queue, observer, reward-normalization statistics and accumulated returns, Python/NumPy/Torch RNGs and training counters. A restart restores the latest committed snapshot and repeats only uncommitted work. Tests require exact equality to uninterrupted training, including a time-limit auto-reset. Partial writes cannot replace the last good pointer; corrupt or changed-source checkpoints are refused.
3. Evaluation now saves and verifies each completed episode independently. An incomplete episode is deterministically rerun; completed evidence is never silently replaced. Training checkpoints are saved and, with --publish, committed/pushed every10,000 new steps. In-flight work after that boundary is not claimed to be saved.

## Why the previous PPO gain was small

- Only 4,029/164,820 recorded v11 control ticks had learned authority. Nominal cost rejection occurred on29277/32964ticks. The candidate must improve the declared balanced predicted cost before the supervisor applies it.
- Residuals are restricted to five values between-0.08and+0.08rad, filtered at0.3s and multiplied by at most0.25. At40ms response age only one10ms control tick remains before50ms expiry. At100ms, learned authority is exactly zero by design. These are architectural constraints, not software exceptions to remove to obtain20%.
- The inherited v11 policy has mean entropy 0.3463 nats versus a five-action maximum1.6094; 40.39% of visited queries assign more than99% probability to one action. Low initial exploration is a plausible learning bottleneck. These associations do not establish a unique causal explanation.
- The supervisor and compensation use a nominal linear bicycle while the software plant has nonlinear tires and stiffness mismatch. The model-based causal planner is a tested comparator, not a globally optimal ceiling. More expressive robust/adaptive prediction remains a research question.
- Training rewards lateral error, heading, actual steering rate and effort. A lateral-only20% target can conflict with smoothness and heading constraints. A submitted action receives gradient credit even if delayed or subsequently rejected; the existing mask correctly removes busy-worker actions, but submitted-request credit can have low signal. Changing this estimator or the objective requires a separately validated experiment.

## Frozen experiment and results

Six final endpoints: two arms x three seeds x50,000 additional steps =300,000 NEW steps. continued preserves the v11 actor/critic/Adam/reward normalization and uses the corrected forecast. explore additionally divides initial action-head weights/bias by4and resets only its Adam slots. The latter is an exploration experiment, not a bug fix. Initial greedy actions and critic parameters remain identical; both arms use identical hyperparameters, matched per-pair RNG/noise, freshness, authority limits, reward and final-endpoint policy. No seed mixing, budget extension or best-checkpoint selection.
1200 fresh matched development episodes, 1,648,200 replayed transitions, 563,760 single-row neural decisions, 216 exact100ms/LQR trajectory pairs. Every normal comparator uses the corrected forecast and same information. legacy_prior is the numerical A/B using the unchanged v11 forecast and weights.

| Controller | Tracking gain vs LQR | Heading change vs LQR | Steering-rate change vs LQR | Survived |
|---|---:|---:|---:|---:|
| lqr | +0.0000% | +0.000% | +0.000% | 120/120 |
| negative | -0.5921% | -1.228% | -1.051% | 120/120 |
| positive | -0.5921% | -1.228% | -1.051% | 120/120 |
| student | +0.4054% | -0.158% | +0.152% | 120/120 |
| oldppo | +0.3275% | -0.178% | +0.131% | 120/120 |
| prior | +0.0431% | -0.193% | +0.014% | 120/120 |
| legacy_prior | +0.0420% | -0.193% | +0.014% | 120/120 |
| planner | +1.0126% | -1.098% | -1.963% | 120/120 |
| continued | +0.0082% | -0.234% | +0.032% | 120/120 |
| explore | -0.1127% | -0.247% | -0.157% | 120/120 |

**continued:20% requirement FAIL.**

Matched gains: lqr +0.0082%, negative +0.5968%, positive +0.5968%, student -0.3987%, oldppo -0.3203%, prior -0.0349%, planner -1.0147%.
Failed checks: less_than20pct_vs_lqr; nonpositive_pair2_vs_lqr; less_than20pct_vs_negative; less_than20pct_vs_positive; less_than20pct_vs_student; nonpositive_pair0_vs_student; nonpositive_pair1_vs_student; nonpositive_pair2_vs_student; less_than20pct_vs_oldppo; nonpositive_pair0_vs_oldppo; nonpositive_pair2_vs_oldppo; less_than20pct_vs_prior; nonpositive_pair0_vs_prior; nonpositive_pair1_vs_prior; nonpositive_pair2_vs_prior; less_than20pct_vs_planner; nonpositive_pair0_vs_planner; nonpositive_pair1_vs_planner; nonpositive_pair2_vs_planner.

**explore:20% requirement FAIL.**

Matched gains: lqr -0.1127%, negative +0.4765%, positive +0.4765%, student -0.5202%, oldppo -0.4417%, prior -0.1559%, planner -1.1369%.
Failed checks: less_than20pct_vs_lqr; nonpositive_pair2_vs_lqr; less_than20pct_vs_negative; less_than20pct_vs_positive; less_than20pct_vs_student; nonpositive_pair0_vs_student; nonpositive_pair1_vs_student; nonpositive_pair2_vs_student; less_than20pct_vs_oldppo; nonpositive_pair0_vs_oldppo; nonpositive_pair1_vs_oldppo; nonpositive_pair2_vs_oldppo; less_than20pct_vs_prior; nonpositive_pair0_vs_prior; nonpositive_pair1_vs_prior; less_than20pct_vs_planner; nonpositive_pair0_vs_planner; nonpositive_pair1_vs_planner; nonpositive_pair2_vs_planner.

Unchanged v11 weights, corrected versus legacy forecast: +0.00109% tracking gain on the same grid. Numerical accuracy and empirical controller superiority are separate outcomes.

## Evidence limits and next work

No final controller is promoted by this audit. Reserved/unseen-path tests remain unopened. The replay uses the recorded inputs and code dynamics, with independent metric aggregation; it is not an independent physical simulator. New controller timing/native Webots/actual laptop and physical sensor–communication–actuator validation remain unperformed. A full matched robust published vehicle controller/MPC reproduction and remaining bibliography verification are still required. No20% all-baseline claim, deployment readiness, hard real-time guarantee or global stability proof follows from surviving software episodes.

The next useful development task is to establish repeatable balanced headroom with a causal model-based controller and measure action-level predicted versus realized benefit under model mismatch. An additional learning method should be judged against that strong controller. Repeatedly extending PPO training until a selected result crosses20% is not an evidence-backed fix.

## Resume

```bash
cd /workspace/LANS
/workspace/lans-venv/bin/python tools/reviewer_v12/run12.py --publish
```

The same command verifies frozen inputs, loads completed training checkpoints, skips verified completed stages, resumes episode-level evaluation, verifies results and republishes the report. Exit2 means the empirical20% target failed, not that the pipeline crashed. Check RESUME.md and status.json for the last completed stage. Cloud storage alone cannot protect unpushed work after the most recent checkpoint.

## Supplemental audit and guarded resume


The initial frozen verifier stopped on NumPy boolean subtraction; `verification.log` preserves that failure.
The corrected verifier compares boolean/integer fields exactly and keeps the same1e-11floating tolerance.
All original episodes, models and acceptance criteria are preserved. See `verifier-repair.json` and `verification-corrected.log`.

Actual checkpoint verification replays steps10,000–20,000 in a separate process and exactly matches actor/critic,
Adam, full environment/queue, normalization and Python/NumPy/Torch RNG. This is verification work, not an extra selected endpoint.
See `resume-replay.json`. Detailed source review is in `semantic-review.md`; software requirements are in `software-environment.json`.

The preferred cloud resume command checks software versions and prevents concurrent guarded runners:

```bash
/workspace/lans-venv/bin/python tools/controller_review/resume_ppo_audit12.py --publish
```

Use `--verify-only` to check completed source/evidence hashes without training or evaluation.
The finite training budget remains exhausted. Work since the last committed10k-step snapshot may be replayed after interruption.

A separate posthoc v11 branch audit checks one packet’s planned assistance until expiry followed by LQR continuation. Its nonlinear software plant, estimator and future recorded noise differ from the nominal predictor. These are conditional diagnostic samples, not population error rates or a deployable oracle.

| State group | Samples | Physical cost benefit >0.1% | Physical cost harm >0.1% |
|---|---:|---:|---:|
| nominal/accepted | 24 | 20 | 3 |
| nominal/cost | 24 | 3 | 12 |
| tire/accepted | 18 | 8 | 4 |
| tire/cost | 24 | 4 | 10 |

This supports investigating prediction/estimation mismatch jointly; it does not isolate either cause or justify bypassing the supervisor.
