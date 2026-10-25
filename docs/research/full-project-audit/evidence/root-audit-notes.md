# Active root/tool audit

Inspected active corrected root plant/residual fusion, LQR/measurement model, observation builder, policy bundle loader/writer, corrected trainer/comparison/benchmark/reporting and visualization; reviewed existing root and ARIS regression tests. Did not retrain, modify archived models/results or change research integration. These modules are separate from the isolated research evaluator and cannot explain the reported ~2% plateau.

Confirmed and fixed:

1. `tools/controller_review/report.py`: paired-condition keys included `noise_seed` but omitted current revision8/9 `noise_id`. Two rows with the same optimization seed but different measurement-noise IDs were silently accepted as paired LQR/student evidence. Added `noise_id` to pair keys; real revision8/9 inputs still validate. Added explicit schema failure when scheduled horizon lacks executed-step/raw-RMSE columns, replacing an incidental KeyError.
2. `controllers/policy_bundle.py`: save_bundle hardcoded a residual contract even for a full-command PathTrackingEnv/Box[-.5,.5] model, and load checked only dimensions. Reject full-command environment contracts at save and require normalized residual Box[-1,1] at save/load. No model is relabeled. Existing corrected smoke bundle loads and predicts successfully.
3. `tools/controller_review/compare.py`: run('residual', ..., policy=None) silently measured LQR under a residual label; arbitrary method names also executed LQR. Both now fail explicitly. Recorded summaries now include executed RMSE and scheduled1000-step horizon so the independent report can validate penalty arithmetic. Nonnegative integral delay is required.
4. `envs/path_tracking_env.py`: changing target_speed mid-episode updated physical speed/gain but left observation error rates at the old speed until the next physical transition. Refresh derived state immediately; unchanged-speed resets remain compatible.
5. `controllers/observation_builder.py`: accepted lookahead_steps=5 then indexed beyond its fixed9-component observation. Enforce the documented fixed four-preview/11-feature contract at construction.

Tests: 7 new tests in tests/test_full_audit_root.py pass; 6 existing controller-remediation and 7 existing ARIS evidence contracts pass (20 total). Independent summarize calls accept all revision8 (30 regional groups) and revision9 (42 groups) paired records. Git diff check clean.

No effect-size gain is inferred from these repairs. No full project/no-bugs claim is justified by this bounded module audit.
