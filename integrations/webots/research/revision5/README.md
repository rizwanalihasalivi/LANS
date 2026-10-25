# Controller review diagnostics and execution interface repair

See the [issue-by-issue remediation record](../../../../docs/research/controller-remediation.md) for L1–L8 and R1–R10, root-pipeline migration and reproduction commands.

- `audit.py`: all72 development cells × seven candidates =504 paired episodes; cloned-state predictor audit on LQR trajectories. Calls the frozen LQR loader and asserts reference parity.
- `report.py`: validates216 historical reference rows and source hashes, then reports all methods, seed/region comparisons and false acceptance/rejection counts.
- `execution.py`: shared simulated single-worker packet lifecycle plus frozen supervisor; exposes held/pending packet and gate context.
- `execution_env.py`:20-feature, execution-aware residual environment. Optional domain randomization; actor/LQR/gate share measured speed. Logs actual fused command, actuator response, packet origin and reward components.
- `smoke_train.py`:1000-step smoke only, recording transitions, advantages and SB3 optimization diagnostics. No performance selection.
- `robust_gate.py`: separate fixed nonlinear model-bank predictor; requires improvement in every declared bank member. It receives no hidden scenario parameters and is not a safety certificate.
- `robust_run.py`:144-episode paired comparison against the stored frozen-gate reference grid; no automatic promotion.
- `test_execution.py`, `test_robust_gate.py`: packet identity, fallback, gate parity, reproducibility, reward accounting and model-bank acceptance contracts.

[Predictor/nonlearned results](../../results/revision5-audit/report.md) · [Separate model-bank results](../../results/revision5-robust/report.md).

Original revision2–4 sources/results remain frozen. The initial diagnostic omitted the selected LQR loader; its output is retained in `revision5-audit-invalid-config` and excluded from conclusions. Corrected freeze `b86cfa8` asserts historical parity. Model-bank design freeze `d29089a` precedes its comparison. No final reserved seed, full research training or native Webots transfer is used in this revision.

## Execution-aware development evaluation

`evaluate_execution.py --policy PATH/policy.zip --seeds 101 --output NEW_DIRECTORY` runs the exact 20-feature training environment and rejects incompatible policy metadata. It evaluates known random-sine development cases at 0/10/20/100 ms, retains paired LQR rows and packet/reward traces, and uses explicit failure-tail scoring. This is not reserved or native evaluation. `test_evaluation.py -v` checks training/evaluation command, reward and packet parity. See the [subsequent ARIS remediation](../../../../docs/research/aris-remediation.md) for captured results and limits.
