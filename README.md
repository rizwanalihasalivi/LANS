# LANS — latency-aware hybrid control research

LANS studies whether learned steering corrections can improve a strong LQR tracker while a supervisor rejects stale or unhelpful commands. Current evidence supports modest, condition-dependent gains from the frozen gated controller. It does not establish PPO dominance, general stability, real-vehicle safety, automotive deployment readiness or a universal inference rate.

The [controller review](docs/research/controller-review/README.md) identifies correctness defects in the historical root pipeline and separate limitations in the isolated research experiments. The [remediation record](docs/research/controller-remediation.md) documents corrected interfaces, quarantined comparisons, fresh diagnostics and remaining evidence limits. Historical comparative claims made by retired root scripts should not be cited as validated results.

## Current evidence and entry points

- [Specification](docs/research/specification-v0.1.md): research requirements; unchanged by remediation.
- [Cloud setup](tools/cloud/README.md): dependency and environment instructions.
- [Webots validation history](docs/research/webots-validation.md): simulation configuration, units, results and native-transfer limitations.
- [Frozen gated surrogate results](integrations/webots/results/revision2-test/report.md) and [native results](integrations/webots/results/revision2-native-test/report.md).
- [Range-matched retraining](integrations/webots/results/revision3-600k/report.md): flat/mixed development trend; no full-budget follow-up.
- [Gate-aware and relative-reward pilots](integrations/webots/results/revision4-pilots/report.md): new arms did not beat the pilot baseline.
- [Predictor and nonlearned-control diagnostics](integrations/webots/results/revision5-audit/report.md): explicit attribution controls on development data.

## Corrected root demonstration

The corrected world-coordinate plant is a separate linear-tire demonstration, not the nonlinear Webots research surrogate. Full steering is applied once by `PathTrackingEnv`; `ResidualPathEnv` owns one LQR-plus-residual fusion. Old root checkpoints are incompatible and must not be reused as corrected policies.

```bash
python tests/test_controller_remediation.py -v
python tools/controller_review/train.py --steps 1000 --output /tmp/lans-corrected-bundle
python tools/controller_review/compare.py --bundle /tmp/lans-corrected-bundle --output /tmp/lans-corrected-comparison
python tools/controller_review/benchmark.py --bundle /tmp/lans-corrected-bundle --output /tmp/lans-inference.json
```

The 1000-step example verifies the pipeline, not policy quality. Output locations must be new. Learned control requires a versioned policy/normalization bundle; missing or incompatible models fail explicitly. Wall inference duration and simulated action age are reported separately. Five-seed full research training requires the predeclared development evidence; it is not launched by these examples.
