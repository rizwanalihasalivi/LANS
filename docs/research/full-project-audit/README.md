# Full project audit and corrections

Audit date: 25 October 2026. Branch: `audit/full-project-corrections`.

**Thirteen categories of confirmed defects were repaired. All 92 tests in 21 suites pass.** New corrected development replays completed with 72/72 and 8/8 surviving trajectories; two private native Webots interface smoke cases also passed. Historical models, source snapshots and raw results remain unchanged.

The audit does **not** establish a hidden bug whose removal produces 5–10% improvement. The broader recorded supervised hybrid gains remain approximately 2.07–2.16%; PPO fine-tuning did not improve them. A real timestamp defect affected the later slow-query diagnostics, but correcting it reduced their estimated benefit. Those diagnostics are superseded by the separate corrected outputs linked below.

## Scope and evidence

The audit started from `048ee96a033f68ea4b285ec6bec33c5256994ac3`, fetched GitHub and merged current `origin/main` (`2c85e4a`) into the separate audit branch. The resulting inventory baseline is `5c3a55da1e8f1bd4398ad906405f210b82203103`. Timestamp changes were committed as `0e4848a38a08c6d1b69b33a675427c068243957a` **before** the corrected diagnostic runs. Other fixes were validated in the same worktree before the final audit commit.

Five parallel workstreams inspected active root control/evaluation, learning, simulation execution, native Webots boundaries, and evidence/reporting. A final read-only cross-review found no additional concrete regression in the changed execution, selection, cleanup and telemetry code. This was a focused code review, not independent ARIS acceptance.

The tracked-baseline [census](evidence/evidence-census.json) covered 6,421 paths:

| Check | Coverage | Result |
|---|---:|---|
| Python syntax | 1,293 files; 165 distinct byte contents | All parse |
| Strict JSON parsing | 2,218 files | No invalid syntax or NaN/Infinity constants |
| CSV/CSV.gz structure | 1,339 files; 1,117,845 data rows | No width/parsing errors or invalid penalized RMSE values |
| Current documentation relative links | Selected root/research navigation | No missing targets at inventory time |
| Historical native raw metric verification | 75 cases | All consistent with recomputed tracking metrics |
| Revision8/9 raw headline recomputation | 540 / 756 episode rows | Recorded means and survival match |

Syntax and file-structure checks are not semantic review of every archived source copy. Active control/training/evaluation paths received targeted inspection and regression tests. External URLs and Markdown anchors were not checked. Full inventory and claim-review details are in the [evidence audit](evidence/evidence-audit-notes.md).

## Confirmed defects and repairs

| # | Defect and consequence | Repair and regression evidence |
|---|---|---|
| 1 | Root report pairing omitted current `noise_id`; different sensor-noise streams could be accepted as paired evidence. | [Report](../../../tools/controller_review/report.py) includes the actual noise identity and checks penalty-schema completeness. Root regression suite rejects mismatched streams. |
| 2 | Bundle writing could label a full-command policy as residual; equal dimensions did not prove the action contract. | [Bundle writer/loader](../../../controllers/policy_bundle.py) verifies residual environment, normalization, 11 observations and normalized `Box[-1,1]` actions. No historical policy was relabeled. |
| 3 | Missing residual policy or an unknown comparison method silently executed LQR under a misleading label. | [Comparison runner](../../../tools/controller_review/compare.py) rejects both, validates delay, and records executed RMSE and scheduled horizon for independent penalty checks. |
| 4 | Changing target speed during an episode left derived observation rates stale until the next transition. | [Environment](../../../envs/path_tracking_env.py) refreshes those rates immediately. Regression checks observations against the new speed. |
| 5 | Observation builder accepted unsupported preview counts and could index outside its fixed observation. | [Builder](../../../controllers/observation_builder.py) enforces its four-preview, 11-feature contract at construction. |
| 6 | Revision4 screening could aggregate incomplete/duplicate scenario grids, including a vacuous severe-delay check. | [Screening](../../../integrations/webots/research/revision4/run_pilots.py) validates complete, unique, finite, noise-paired grids before comparisons. Four tests include exact parity with recorded B/C/D decisions. |
| 7 | Revision9 selection omitted severe-delay fallback eligibility and trusted incomplete/positionally paired input. | [Selection](../../../integrations/webots/research/revision9/evaluate9.py) checks the full 1,188-row development grid, explicit per-cell fallback, noise pairing and canonical ordering. All historical selection dictionaries remain exactly unchanged. |
| 8 | Revision10/11 queried policies every 50 ms but resubmitted held proposals every 10 ms with fresh timestamps. This hid up to 40 ms of observation age. | Optional explicit submission control in [execution](../../../integrations/webots/research/revision5/execution.py) and [kernel](../../../integrations/webots/research/revision7/kernels.py); live and forecast loops submit only on real query ticks. Existing every-tick callers preserve their default behavior. New tests cover parity, retained age and delivery between query ticks. |
| 9 | Worker startup errors/timeouts and controller exceptions could leak processes/queues/logs. | [Worker](../../../integrations/webots/research/worker.py) cleans failed initialization and closes idempotently; controllers register cleanup immediately. Invalid delays/nonfinite timestamps reject. Injected failures and a real spawned worker exercise cleanup. |
| 10 | Launcher timeout killed only the shell, leaving simulator/display descendants running. | [Process helper](../../../integrations/webots/research/native_process.py) owns a process group, terminates the group and reaps its launcher. Real parent/grandchild timeout test passes. Non-child zombies still depend on host reaping. |
| 11 | Same-name native cases in separate output directories could collide on a generated world. | [Physical runner](../../../integrations/webots/research/run-physical.py) keys private projects by resolved output path. Regression verifies separate destinations produce separate worlds. |
| 12 | Native analysis trusted summarized RMSE/max without checking the raw telemetry. | [Analyzer](../../../integrations/webots/research/analyze-physical.py) recomputes tracking/failure-penalty metrics, validates counts and handles one-row traces. A corrupted real-fixture summary is rejected. |
| 13 | Held policy packets were counted repeatedly in inference-time quantiles. | Analyzer deduplicates inference packets; control-tick action-age statistics remain tick-based. Regression distinguishes two actual inferences from eleven held-packet rows. |

Detailed notes: [root](evidence/root-audit-notes.md), [learning](evidence/learning-audit-notes.md), [simulation](evidence/simulation-audit-notes.md), [native](evidence/native-audit-notes.md). These contemporaneous notes retain original `/tmp` evidence locations; their files are copied into this directory. Historical reports and source snapshots are preserved, including their old semantics. Current navigation points readers to corrected evidence. Current revision11 report headings were also repaired.

Root/native/selection repairs improve correctness and evidence reliability; they do not explain the earlier isolated surrogate gain. The timestamp defect affects the slow-query revision10/11 drivers, not revision8/9's default every-available-tick submission interface.

## Corrected diagnostic results

The original protocols, controller weights, student models and development noise IDs were retained for correction/replay. No final-test data were used for tuning and no training was launched. Replays write to new directories.

### Revision10: 72 complete development episodes

[Corrected report and raw evidence](../../../integrations/webots/results/full-project-audit/revision10-corrected/report.md), executable freeze `0e4848a`.

| Method | Survival | Mean penalized RMSE (m) | Reduction versus paired LQR |
|---|---:|---:|---:|
| LQR | 12/12 | 0.101342 | — |
| Fixed −0.04 rad proposal | 12/12 | 0.100952 | 0.384% |
| Frozen student | 12/12 | 0.100906 | 0.430% |
| 200 ms held-action teacher | 12/12 | 0.101155 | 0.184% |
| 400 ms held-action teacher | 12/12 | 0.100864 | 0.471% |
| 400 ms beam-sequence teacher | 12/12 | 0.100864 | 0.471% |

All severe 100 ms cases revert exactly to LQR. This is one known DLC at 25 m/s, six conditions and two paired noise repetitions; it is not the broader revision8/9 evaluation. The 400 ms held teacher's earlier 0.635% becomes **0.471%** after the timing correction. Its tire-mismatch mean remains **0.642% worse** than LQR. No regional mean reaches 5%. Longer preview alone has not demonstrated the missing benefit.

### Revision11: eight complete attribution trajectories

[Corrected report and raw branches](../../../integrations/webots/results/full-project-audit/revision11-corrected/report.md), executable freeze `0e4848a`.

All 8/8 trajectories survive; 11,283 branch rows cover 5,280 sampled state/candidate/horizon groups, with no failed branches. On tire-mismatch student-behavior states, 32 accepted shadow decisions include **11 with meaningful lateral harm**; among 388 cost rejections, **26** have a ramp-allowed intervention with meaningful lateral benefit. Another 13 helpful cases are withheld by recovery/persistence rules. Of 1,004 available tire comparisons, 78 switch from helpful at 200 ms to harmful at 1 s.

These are correlated offline interventions using privileged future noise, not independent trials, actual deployed-policy failure probabilities, or proof that removing a gate restriction would improve full episodes. Predictor mismatch combines nominal dynamics, local curvature, estimation and reference differences. The results justify a controlled predictor/objective experiment, not an authority increase.

## Why the result remains near 2%, not 5–10%

The [independent metric recomputation](evidence/evidence-metrics.json) confirms these existing broad surrogate results:

| Frozen evidence | LQR RMSE (m) | Compared controller RMSE (m) | Reduction |
|---|---:|---:|---:|
| Revision8 supervised student | 0.08443437 | 0.08261215 | 2.158% |
| Revision8 finite privileged teacher | 0.08443437 | 0.08255104 | 2.231% |
| Revision9 retained student | 0.08430677 | 0.08256349 | 2.068% |
| Revision9 100k PPO fine-tuning endpoint | 0.08430677 | 0.08282999 | 1.752% |

The current student is a supervised residual proposal policy; it should not be described as standalone PPO success. Development selection retained **step 0 for all fine-tuning seeds**. The new selection guards reproduce that decision exactly.

**The student is already close to its finite teacher.** The revision8 teacher improves RMSE over the student by only approximately 0.074%. That teacher searches five residual actions over 200 ms with three forecasts and the existing gate. It is an approximate privileged comparator, not an absolute controller ceiling. Simply fitting that same teacher more accurately has little demonstrated benefit left in these recorded results.

**Tire mismatch carries much of the remaining error.** It accounts for 34.61% of the sum of six regional LQR means, while the student's reduction there is only 1.513%. Holding all five other recorded regional results fixed, reaching 5% overall would require approximately 9.72% tire-region improvement; reaching 10% would require approximately 24.17%. This is descriptive arithmetic about target size, not a tuning prescription derived from final tests or a forecast that those gains are feasible.

**PPO fine-tuning changes behavior and drifts from the useful initialization.** On the existing 24,300 development observations, sampling from the student logits instead of taking argmax produces a non-argmax action about 11.7–12.1% of the time and increases expected finite-teacher regret for all three seeds. See the [probe and results](evidence/learning-stochastic-diagnostic.json). This is normal PPO exploration, not a software bug. Recorded final actor agreement falls to 92.01%, 82.14% and 82.82%, with worse teacher regret. Per-update target KL does not permanently anchor the actor to the original student.

**Useful learning opportunities are limited under the current objective.** Recorded fine-tuning gate activity is about 6.6–8.9%; mean tracking reward is about 0.96 while mean relative-improvement reward is about 0.0005–0.0007. These scales and actor drift are consistent with weak action-dependent credit, but means alone do not establish gradient dominance or causality. The audit found no evidence of wrong actor transfer, optimizer reset, missing normalization, doubled LQR, or a wrong ±0.08 mapping in this current learning path.

**Severe-delay fallback is not the main numerical explanation.** Excluding the revision8 100 ms fallback region raises the student gain only from 2.158% to 2.461%, and the teacher to 2.544%. It does not reveal a hidden 5% result; the declared primary metric remains unchanged.

The strongest next research step is a separately frozen development ablation of predictor geometry/dynamics versus decision objective, with the current gate and simple nonlearned corrections as references. Judge whole episodes, including nominal performance, survival, tire mismatch and exact severe-delay fallback. Only a repeatable development gain should justify new teacher/student targets or PPO pilots; large training budgets and more PPO authority are not supported by this audit. No new objective or threshold was selected against existing reserved results.

## Validation and reproduction

The [consolidated log index](checks/summary.json) records **92 passing tests in 21 suites**. It includes new regression cases, prior root/ARIS contracts, adapter units, native failure injection, and revision2–11 contracts. A real spawned worker additionally passed one-in-flight, delayed delivery, subsequent submission and shutdown checks ([evidence](evidence/lans-native-worker-functional.json)).

Two actual private Webots smoke cases used LQR and the **legacy** gated residual model at 20 m/s on a nominal DLC, noise seed 880501, for 3 seconds/300 control ticks after 10 seconds warmup. Both survived; RMSE was 0.051640932 m and 0.050709710 m. These are interface smoke numbers, not a comparative advantage claim. [Raw native outputs](../../../integrations/webots/results/full-project-audit/native-smoke/summary.json) and the [executed smoke script](evidence/lans-native-smoke-check.py) are retained. The smoke exercised the corrected worker/controllers before the process-group helper was added; that helper was subsequently verified with a real descendant-process timeout test. The separate [75-case raw recheck](evidence/lans-native-metric-audit.json) did not rewrite archived native metrics.

From repository root, use the pinned Python environment described in [cloud setup](../../../tools/cloud/README.md). This workspace used `/workspace/lans-setup/venv/bin/python`; substitute the matching interpreter on another machine. Each output path must be new.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-audit-reproduction-numba
export MPLCONFIGDIR=/tmp/lans-audit-reproduction-mpl

/workspace/lans-setup/venv/bin/python tools/controller_review/full_audit_checks.py \
  --output /tmp/lans-audit-checks-new

/workspace/lans-setup/venv/bin/python integrations/webots/research/revision10/run.py \
  --output /tmp/lans-audit-r10-new
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision10/report.py \
  --run /tmp/lans-audit-r10-new

/workspace/lans-setup/venv/bin/python integrations/webots/research/revision11/run.py \
  --output /tmp/lans-audit-r11-new
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision11/report.py \
  --run /tmp/lans-audit-r11-new

/workspace/lans-setup/venv/bin/python \
  docs/research/full-project-audit/evidence/learning-stochastic-probe.py \
  --repo "$PWD" --output /tmp/lans-audit-stochastic-new.json
```

The native smoke script records the exact workspace and fresh output paths used; update its `root` and `output` variables in a private copy before replaying elsewhere. Native replay also requires the repository's private runtime configuration in the [native runner instructions](../../../integrations/webots/research/revision2/native/README.md). No shared Webots installation change is needed.

## Remaining limitations

- This is a broad, bounded audit with targeted runtime coverage; it cannot certify that every possible bug is absent.
- Historical reproduction still lacks eight original supplement files and the external `/mnt/data/lans_work` dependency described in [reproduction status](../../../research-inputs/REPRODUCTION_STATUS.md). Missing originals cannot be repaired by inventing files or results.
- The native worker remains an explicit legacy 9-feature policy interface. The current supervised 20-feature student has not been transferred or validated there; the smoke must not be cited as that transfer.
- Corrected attribution is a small, correlated development diagnostic. Broader generalization, real vehicle safety and 5–10% gains remain unproven.
- No old model, reserved result, primary specification, `experiments/phase1/` artifact or shared Webots installation was modified. No new expensive training or repeated final-test-based model selection was performed.
