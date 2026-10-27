# LANS — latency-aware hybrid control research

LANS studies whether learned steering corrections can improve a strong LQR tracker while a supervisor rejects stale or unhelpful commands. Current evidence supports modest, condition-dependent gains from the frozen gated controller. It does not establish PPO dominance, general stability, real-vehicle safety, automotive deployment readiness or a universal inference rate.

The [controller review](docs/research/controller-review/README.md) identifies correctness defects in the historical root pipeline and separate limitations in the isolated research experiments. The [remediation record](docs/research/controller-remediation.md) documents corrected interfaces, quarantined comparisons, fresh diagnostics and remaining evidence limits. Historical comparative claims made by retired root scripts should not be cited as validated results.

The subsequent [ARIS audit remediation](docs/research/aris-remediation.md) retires unsupported result generators, fixes plotting, adds raw-data reporting and execution-aware evaluation, and records the remaining original-archive blocker.

The [full project audit and corrections](docs/research/full-project-audit/README.md) records 92 passing contract tests, corrected slow-query timestamps, verified raw metrics and remaining evidence limits behind the roughly 2% student gain.

## Current evidence and entry points

- **Latest single pipeline:** [matched causal-state retraining, full replay and status](docs/research/reviewer-pipeline-v9/README.md).
  Six fixed pilots add 600,000 training steps; all 1,080 fresh development
  episodes survive and 1,483,380 transitions / 563,760 neural decisions replay.
  The new causal-history PPO gains 0.230% over LQR but is 0.034% worse than
  the compensated student, so scientific selection still fails. The
  predeclared diagnostic actor records **0/7,500 original 10ms deadline
  misses**, with functional fallback and full history/query/gate replay.
  This finite cloud result is not target-laptop or hard-real-time evidence;
  earlier failed campaigns remain preserved. An initial one-decision float32
  batch/single-row audit discrepancy is documented and corrected by exact
  single-observation replay, with no episode reruns or relaxed criteria.
  [Python 3.10 Windows/macOS kit](docs/research/reviewer-pipeline-v9/LANS_Causal_Python310_Kit.zip)
  and [Word/PDF evidence reports](docs/research/reviewer-pipeline-v9/LANS_Pipeline_Reports.zip).
  Run `python tools/controller_review/run_single_pipeline.py --publish` in
  the research environment. Exit 2 explicitly retains unmet scientific or
  external requirements; reserved/native, matched robust-vehicle reproduction,
  primary references and physical/target evidence are not silently passed.
- **Prior recovery/expiry study:** [full matched matrix and deadline guard](docs/research/reviewer-recovery-v8/README.md).
  Recovery now requires three distinct qualifying proposals across bounded gaps,
  with zero authority on stale ticks. Prediction uses only the current packet's
  eligible lifetime, then LQR continuation. All 840 episodes survive and
  1,153,740 transitions replay. Compensated PPO gains 0.295% over LQR and 0.024%
  over the matching student; full selection fails. Guard timing has 1/7,500
  original-deadline misses; the randomized unguarded arm has 2/7,500. A separate
  one-second worker-stall/recovery test passes all three seeds with 0/2,400
  misses. These finite windows are not WCET or vehicle certification.
  [Updated three-actor Python 3.10 kit](docs/research/reviewer-recovery-v8/LANS_Recovery_Python310_Kit.zip)
  and [Word/PDF evidence reports](docs/research/reviewer-recovery-v8/LANS_Recovery_Reports.zip)
  preserve failures. Resume with
  `python tools/controller_review/run_recovery_work.py --publish`.
- **New experimental component:** [explicit neural-response delay compensation](docs/research/reviewer-delay-compensation-v7/README.md).
  Supervisor-owned model forecasting supplies predicted physical PPO inputs
  over a causal estimate from completed-response history. The horizon is capped
  at 40ms; original timestamps and the 50ms stale cutoff remain unchanged.
  All 72 diagnostic episodes and 93,600 transitions replay. Tracking gain
  versus raw PPO is +0.471% at 20ms logical service and -0.116% at 10ms;
  40/100ms cases have no learned authority. This is approximate input
  compensation, not physical delay cancellation or a promoted controller.
  [Experimental Python 3.10 kit](docs/research/reviewer-delay-compensation-v7/LANS_Delay_Compensation_Python310_Kit.zip)
  uses the explicit `delay_compensated` profile and unchanged frozen weights.
  Earlier frozen timing studies require their recorded source snapshots/commits;
  current v7 source must not be relabeled with their old hashes.
- **Latest submitted-action study:** [matched credit ablation and timing attribution](docs/research/reviewer-credit-v6/final-update.md).
  Six fixed pilots add 600,000 transitions; all 672 fresh development episodes
  survive and 922,992 transitions independently replay. Submitted-only PPO gains
  2.611% over LQR, but just 0.561% over the student, below the frozen 1% margin.
  No arm qualifies. The separate diagnostic misses 657/7,500 controller deadlines;
  the native heartbeat misses 587/3,000. Functional fallback passes; reserved
  confirmation stays unopened. A verified scalar robust-filter specialization
  and all-32-entry bibliography audit do not constitute the matched robust
  vehicle reproduction or complete primary-source verification.
  [Three-actor Python 3.10 kit](docs/research/reviewer-credit-v6/LANS_Current_Python310_Kit.zip)
  and [Word/PDF evidence reports](docs/research/reviewer-credit-v6/LANS_Credit_Reports.zip)
  remain research diagnostics. Resume with
  `python tools/controller_review/run_credit_work.py --publish`.
- **Latest matched history ablation:** [600,000 additional transitions and 672 fresh episodes](docs/research/reviewer-history-v5/final-update.md).
  The balanced no-history diagnostic gains 2.956% over LQR, with 0.52% lower
  heading error and 4.73% higher actuator-rate RMS. Its 0.943% student-relative
  gain misses the unchanged 1% requirement. The history variant also fails the
  steering-rate limit. No winner is promoted; reserved tests remain unopened.
  [Python 3.10 diagnostic kit](docs/research/reviewer-history-v5/LANS_History_Python310_Kit.zip)
  and [Word/PDF evidence reports](docs/research/reviewer-history-v5/LANS_History_Reports.zip)
  include the versioned causal input and ABI guards. The 1,500-tick cloud smoke
  has 274 deadline misses; functional fallback passes. Actual laptop and physical
  validation are pending. Resume with
  `python tools/controller_review/run_history_work.py --publish`.
- **Latest deep diagnosis:** [realistic asynchronous delivery and scalar predictor](docs/research/reviewer-interface-v4/final-update.md).
  The unchanged PPO endpoints gain2.579% over LQR, with0.51% lower heading error
  and4.17% higher actuator-rate RMS. The roughly0.57% student-relative gain still
  fails the frozen1% margin. All672 episodes survive; actual one-second worker
  stall/recovery passes functional checks for all three seeds. Deadline tests
  still fail, including the native heartbeat baseline. No candidate is promoted.
  [Updated experimental Python3.10 kit](docs/research/reviewer-interface-v4/LANS_Interface_Python310_Kit.zip)
  uses the fresh-within-deadline authority rule, scalar predictor and actual PPO
  actors in a software plant; it is not vehicle deployment approval.
  Resume with `python tools/controller_review/run_interface_work.py --publish`.
- **Latest aligned study:** [300,000-step training and576-episode comparison](docs/research/reviewer-aligned-v3/README.md)
  passes the balanced-versus-LQR development screen:1.445% tracking gain,
  0.27% lower heading error and2.66% higher actuator-rate RMS (within5%).
  PPO beats the matched student by about0.33%, below the frozen1% margin;
  full promotion fails and reserved tests remain unopened. Timing still fails.
  [Verified report](docs/research/reviewer-aligned-v3/final-update.md) and
  [Python3.10 full-controller kit](docs/research/reviewer-aligned-v3/LANS_Aligned_Python310_Kit.zip)
  include actual v3 actors, exact NumPy export and replay checks.
  [One-command reproduction and limits](tools/controller_review/README-aligned.md).
- **Prior frozen follow-up:** [same-gain attribution and smoothing](docs/research/reviewer-followup-v2/README.md)
  reports864 fresh development episodes. Filtered PPO gains5.79% tracking versus
  LQR, but has27.5% higher actuator-rate RMS and trails the same-gain student.
  Preview filtering gains0.73%; no new variant passes the frozen selection gate.
  [Detailed update](docs/research/reviewer-followup-v2/final-research-update.md)
  separates timing failures, nominal published-filter specialization, laptop kit
  and physical evidence still required. Resume software stages with
  `python tools/controller_review/run_followup_work.py --publish`.
- [Reviewer-response causal residual campaign](tools/reviewer_campaign/README.md):
  one-command staged PPO training, mirrored comparisons, real-worker timing and
  native interface checks, with verified milestones pushed to the research branch.
  [Live evidence and status](docs/research/reviewer-causal-v1/status.json) distinguish
  completed tests from failed criteria and pending physical/reference work.
- [Archived90-episode diagnostic](docs/research/reviewer-pilot-2026-10-26/README.md):
  historical checkpoints only; their old input interface prevents a deployable
  causal-policy claim. Do not mix their numerical gains with the new campaign.

- [Specification](docs/research/specification-v0.1.md): research requirements; unchanged by remediation.
- [Cloud setup](tools/cloud/README.md): dependency and environment instructions.
- [Webots validation history](docs/research/webots-validation.md): simulation configuration, units, results and native-transfer limitations.
- [Frozen gated surrogate results](integrations/webots/results/revision2-test/report.md) and [native results](integrations/webots/results/revision2-native-test/report.md).
- [Range-matched retraining](integrations/webots/results/revision3-600k/report.md): flat/mixed development trend; no full-budget follow-up.
- [Gate-aware and relative-reward pilots](integrations/webots/results/revision4-pilots/report.md): new arms did not beat the pilot baseline.
- [Predictor and nonlearned-control diagnostics](integrations/webots/results/revision5-audit/report.md): explicit attribution controls on development data.

## Correction-quality PPO pilot (revision6)

The [matched600k-step pilot](integrations/webots/results/revision6-correction/interpretation.md) trained two arms at three fresh seeds and evaluated648 paired development episodes. Execution-aware training improved direct-trained error by only0.15%, failed the1% progress screen and did not beat simple fixed corrections. Neither model is promoted. The nominal constrained MPC reference is explicitly limited; LQR also beats it. [Protocol and reproduction](integrations/webots/research/revision6/README.md).

## Step1 headroom diagnostic (revision7)

The [five-action privileged diagnostic](integrations/webots/results/revision7-headroom/interpretation.md) completed864 paired episodes. With the actual frozen gate, measured error is2.076% lower than LQR and1.266% lower than the best global fixed proposal; all108 gated cases survive. The diagnostic bypass fails90/108 cases. These are finite-policy privileged results, **not an absolute ceiling or a trained-student result**. That Step1 diagnostic launched no training; Step2 is recorded below. [Protocol and reproduction](integrations/webots/research/revision7/README.md).

## Step2 supervised pilot (revision8)

The [teacher/student pilot](integrations/webots/results/revision8-student/interpretation.md) removes actual future-noise knowledge from teacher forecasts and trains three sensor/history-only students. On540 fresh paired episodes the student reduces LQR error by2.158% and the predeclared fixed-correction error by1.351%, passing its bounded pilot screen with108/108 survival. These are known task families, not native/safety/general-superiority evidence. Step2 itself launched no PPO fine-tuning, gate change or model promotion. [Protocol/reproduction](integrations/webots/research/revision8/README.md).

## Current Step3 PPO fine-tuning pilot (revision9)

The [matched fine-tuning pilot](integrations/webots/results/revision9-finetuning/interpretation.md) completed600k additional RL steps with exact supervised-actor transfer and a scratch control. All three finetune seeds selected step0 on independent development episodes. On756 fresh final episodes, the retained student reduces LQR error by2.068%; the100k fine-tuned endpoint has0.323% **higher** error than that student. The incremental PPO improvement screen fails. Retain the supervised research checkpoint; no production promotion or gate change. [Chart](integrations/webots/results/revision9-finetuning/comparison.png), [full report](integrations/webots/results/revision9-finetuning/report.md), [protocol/reproduction](integrations/webots/research/revision9/README.md).

## Corrected root demonstration

The corrected world-coordinate plant is a separate linear-tire demonstration, not the nonlinear Webots research surrogate. Full steering is applied once by `PathTrackingEnv`; `ResidualPathEnv` owns one LQR-plus-residual fusion. Old root checkpoints are incompatible and must not be reused as corrected policies.

```bash
python tests/test_controller_remediation.py -v
python tools/controller_review/train.py --steps 1000 --output /tmp/lans-corrected-bundle
python tools/controller_review/compare.py --bundle /tmp/lans-corrected-bundle --output /tmp/lans-corrected-comparison
python tools/controller_review/benchmark.py --bundle /tmp/lans-corrected-bundle --output /tmp/lans-inference.json
```

The 1000-step example verifies the pipeline, not policy quality. Output locations must be new. Learned control requires a versioned policy/normalization bundle; missing or incompatible models fail explicitly. Wall inference duration and simulated action age are reported separately. Five-seed full research training requires the predeclared development evidence; it is not launched by these examples.
