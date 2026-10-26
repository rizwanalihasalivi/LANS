# LANS — latency-aware hybrid control research

LANS studies whether learned steering corrections can improve a strong LQR tracker while a supervisor rejects stale or unhelpful commands. Current evidence supports modest, condition-dependent gains from the frozen gated controller. It does not establish PPO dominance, general stability, real-vehicle safety, automotive deployment readiness or a universal inference rate.

The [controller review](docs/research/controller-review/README.md) identifies correctness defects in the historical root pipeline and separate limitations in the isolated research experiments. The [remediation record](docs/research/controller-remediation.md) documents corrected interfaces, quarantined comparisons, fresh diagnostics and remaining evidence limits. Historical comparative claims made by retired root scripts should not be cited as validated results.

The subsequent [ARIS audit remediation](docs/research/aris-remediation.md) retires unsupported result generators, fixes plotting, adds raw-data reporting and execution-aware evaluation, and records the remaining original-archive blocker.

The [full project audit and corrections](docs/research/full-project-audit/README.md) records 92 passing contract tests, corrected slow-query timestamps, verified raw metrics and remaining evidence limits behind the roughly 2% student gain.

## Current evidence and entry points

- **Latest frozen follow-up:** [same-gain attribution and smoothing](docs/research/reviewer-followup-v2/README.md)
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
