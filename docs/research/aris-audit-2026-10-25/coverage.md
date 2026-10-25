# Coverage and evidence ledger — ARIS audit completion

Reviewed HEAD: `966e034a2868ce122855d86417ecbe67ec1b1120`; date: 2026-10-24 UTC. Reviewer session `/root/aris_audit_completion`. Requested route gpt-6-astra/ultra; actual specific model/effort not independently returned. Same-family/provisional.

This is a completion of an interrupted review, not a fresh full rerun. The original task had 5,200 tracked files and 209 primary files. All tracked paths received the saved census's applicable mechanical checks; a subset received focused semantic inspection. **The requested exhaustive line-by-line read of every evaluation/source file was not completed.** The report does not claim otherwise. Exact duplicates reduce repeated reading but do not turn an AST parse into semantic review.

## Coverage by project category

| Category | Completed checks | Limits |
|---|---|---|
| Root controllers, model, corrected environments, trainer/evaluator/timing | Direct inspection of physical-state propagation, one fusion, units, bundle normalization, previews, seed/speed, delay loop, reward, effective LR and ZOH code; saved current-root diagnostic results examined | No new training. Saved root probes cover 36 stored episodes, four fresh reproductions and 1,000-step parity; other legacy environments and reporting entry points have confirmed remaining defects. Not every auxiliary function was read. |
| Original isolated research campaign (revision1) | Read core plant/reference/sensor/control, original/survival environments, main evaluation/reporting, training and finalization paths; independently aggregate 810 rows and check ten saved checkpoint metadata/source records | No retraining, fresh native physics, independent full optimizer tensor inspection or visual figure audit. Four post-save metadata errors are disclosed and reconciled. |
| Revision2 gate and reserved/native evaluations | Read gate, surrogate evaluator, real worker and gated native controller; aggregate 96 development +900 reserved surrogate +270 native rows; reuse 350 native telemetry metric checks spanning multiple campaigns | Native simulator not rerun. Native runner/analyzer/report source not exhaustively inspected line by line. Same policy seeds/known paths do not create new generalization. |
| Revision3 range matching and continuation | Read mapping, matched environment, 600k continuation and staged-status documentation; aggregate 360 pilot +360 extension +288 confirmation rows; verify 216 unchanged reference rows and stored checkpoint metadata | Later full-training/native launchers mostly mechanical coverage. Unrun planned experiments explicitly remain unrun. Saved large rev123 probe has no completed JSON and is not treated as passed. |
| Revision4 A–D pilots | Read arm environment, reward branches, evaluator, trainer/protocol and report; aggregate504 records; inspect saved5-test pass output; verify72/180 disjoint noise allocation | No repeat pilot training. Four-arm design is not fully factorial. Not all runner/report implementation lines read. Saved large rev45 probe has no completed JSON and is not treated as passed. |
| Revision5 execution/predictor/model bank | Read execution/history, environment/reward logging, attribution audit, robust gate, smoke trainer and reports; aggregate504+144 episode rows; recount15,648 predictor rows; verify216 reference rows and84 severe fallback rows; inspect saved3+3-test pass outputs | Smoke interface has no qualified new policy/native result. No expensive predictor branches or model-bank campaign rerun. All shadow decisions are correlated diagnostics. |
| Docs/research and research wiki | Read current README, remediation, historical review, decisions, uploaded-artifact review and principal result reports; sampled wiki landing/gaps/query | Other design/history documents inventoried, not fully read during completion. Dated historical claims are distinguished from current claims. |
| Cloud/install/simulator integration | Read setup recipe/cloud README, Python installer and actual native worker/controller scheduling; census covers scripts/world snapshots; saved smoke artifacts inventoried | No installs/services, SUMO/Webots/CARLA runs or external downloads. Remaining shell scripts, worlds, adapter/analyzer code were not comprehensively audited. No CARLA server or physical validation inferred. |
| Supplied original manuscript | Preserved DOCX ZIP integrity; inspected extracted abstract, timing, energy and stability claims | Not every paragraph/equation/citation checked; no literature lookup, physical proof or manuscript edit. |
| JSA supplement and submission candidate | ZIP inventory/CRC, extracted source/claim inspection, independent252-row targeted aggregation; verified eight named manifest members absent; checked hardcoded reproduction locations | No execution of supplied reproduction scripts/C binaries, full C-port proof/WCET audit, raw-energy reintegration, or independent reproduction of every historical table. The revised candidate's careful limitations are recognized. |
| Archived source copies and model assets |981 Python files parsed,111 distinct contents grouped;32 checkpoint ZIP step/seed/policy/source provenance comparisons; archived full-policy source diffs reconciled | Not all111 unique source contents semantically read; arbitrary pickle/ELF/model binaries not independently validated. Existing digests checked for consistency, not a new provenance scheme. |
| CSV/JSON/logs/figures/PDF/TensorBoard |764 CSV/CSV.gz files streamed (669,885 records including headers/comments);2,057 JSON parses and1 malformed;738 log scans;39 archive CRC checks; plot/image/PDF/event files inventoried | A parse is not truth verification. Native subset and principal result grids have stronger recomputation. No visual review of eight PNGs or the standalone PDF; six TensorBoard event files not decoded. |

## Evidence preserved and executed commands

Reused **completed** outputs: `census-summary.json`, `census-details.json`, `source-duplicates.json`, `native-metric-checks.json`, `legacy/diagnostics.json`, `rev45-test4.txt`, `rev45-test5execution.txt`, `rev45-test5robust.txt`, and extracted files under `attachments/` and `claims-attachments/`, all in `/workspace/lans-aris-audit/`. The corresponding census/legacy source scripts were inspected. The legacy output records6 passing current-root tests and four bounded fresh root episodes; completion did not run them again.

Saved scripts **without completed result outputs at initial inspection**: `rev123-diagnostics.py` and `rev45_check.py`. Their assertions were read as plans, not reported as successful executions. Completion replaced only the necessary uncompleted evidence checks with bounded CSV/ZIP reads.

Executed during completion:

```bash
/workspace/lans-venv/bin/python /workspace/lans-aris-audit/completion_checks.py
/workspace/lans-venv/bin/python /workspace/lans-aris-audit/completion_provenance_checks.py > /workspace/lans-aris-audit/completion-provenance-output.txt
```

The first command initially creates `completion-check-results.json` with4,236 unique-key principal-grid rows,3,966 reconstructed penalties, exact historical parity, predictor counts, reserved allocation checks, targeted manuscript means and training metadata. The second extends that JSON with32 checkpoint metadata/source consistency records, five expected historical/current source differences and the eight missing supplementary members. An earlier equivalent inline provenance read preceded the persisted script; the saved script was then executed successfully. Existing hashes were checked, not added to project source.

Other executed tools were read-only `rg`, `cat`, `nl`, `sed`, `diff`, `git status/log`, and short Python inventory/aggregation reads. Review output writes were restricted to `/workspace/lans-aris-audit/` and this trace directory. No source/tests, old results or manuscript artifacts were modified; no application training, full native run, installation or push was performed.

Archive line mapping:

- Original manuscript extraction: `/workspace/lans-aris-audit/attachments/LANS0605_英文IEEE格式_0618_updated_1 (1).txt`; source is the matching DOCX in `research-inputs/`.
- Supplement extraction root: `/workspace/lans-aris-audit/claims-attachments/LANS_JSA_Supplementary_Package (2)(4)/LANS_JSA_Supplementary/`; e.g. `FILE_MANIFEST.json:50`, `LANS_JSA_Manuscript.docx.txt`, `sources/`, `historical_results/`, `tables/`.
- Candidate extraction root: `/workspace/lans-aris-audit/claims-attachments/LANS_JSA_Submission_Candidate_Package/`; `LANS_JSA_Submission_Ready_Candidate.docx.txt` preserves P-numbered paragraph identifiers; targeted CSVs are beside it.
- `claims-attachments/index.json` and `attachments/archive-index.json` map originals/archive entries to the inspected extractions. Archive CRC/member checks do not establish executable reproduction.

## Primary-file ledger

“Focused semantic inspection” means source/report content relevant to the findings was read, often in full for compact core files, but **does not assert every line was read**. “Byte-identical” relies on the saved whole-content duplicate grouping. “Machine/inventory only” is explicitly unreviewed semantically in this completion, even if older project reviews discuss it. Contract test outputs and result artifacts can support particular claims without implying their entire implementation was read.

Status counts: Machine/inventory only in completion: 135, Focused semantic inspection: 64, Inventoried; no semantic/visual review: 6, Byte-identical to inspected source: 4.

| Primary file | Completion coverage | Mechanical evidence / note |
|---|---|---|
| `.gitignore` | Machine/inventory only in completion | Path/size inventory only |
| `AGENTS.md` | Focused semantic inspection | Path/size inventory only |
| `README.md` | Focused semantic inspection | Path/size inventory only |
| `ablation_study_real.py` | Focused semantic inspection | python_ast_parse |
| `benchmark_corrected.py` | Focused semantic inspection | python_ast_parse |
| `check_path.py` | Machine/inventory only in completion | python_ast_parse |
| `collect_lans_data.py` | Machine/inventory only in completion | python_ast_parse |
| `collect_lqr_data.py` | Machine/inventory only in completion | python_ast_parse |
| `collect_ppo_data.py` | Machine/inventory only in completion | python_ast_parse |
| `complete_verification.py` | Machine/inventory only in completion | python_ast_parse |
| `controllers/__init__.py` | Machine/inventory only in completion | python_ast_parse |
| `controllers/lans_controller.py` | Focused semantic inspection | python_ast_parse |
| `controllers/latency_monitor.py` | Machine/inventory only in completion | python_ast_parse |
| `controllers/lqr_controller.py` | Focused semantic inspection | python_ast_parse |
| `controllers/observation_builder.py` | Focused semantic inspection | python_ast_parse |
| `controllers/policy_bundle.py` | Focused semantic inspection | python_ast_parse |
| `diagnostic_lqr.py` | Machine/inventory only in completion | python_ast_parse |
| `docs/research/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `docs/research/controller-remediation.md` | Focused semantic inspection | Path/size inventory only |
| `docs/research/controller-review/README.md` | Focused semantic inspection | Path/size inventory only |
| `docs/research/controller-review/aggregates.csv` | Machine/inventory only in completion | csv_full_stream_parse |
| `docs/research/controller-review/audit.py` | Machine/inventory only in completion | python_ast_parse |
| `docs/research/controller-review/diagnostics.csv` | Machine/inventory only in completion | csv_full_stream_parse |
| `docs/research/controller-review/evidence.json` | Machine/inventory only in completion | json_parse |
| `docs/research/controller-review/plot.py` | Machine/inventory only in completion | python_ast_parse |
| `docs/research/controller-review/review-chart.png` | Inventoried; no semantic/visual review | Path/size inventory only |
| `docs/research/controller-review/test-results.txt` | Machine/inventory only in completion | Path/size inventory only |
| `docs/research/decisions.md` | Focused semantic inspection | Path/size inventory only |
| `docs/research/reviews.md` | Focused semantic inspection | Path/size inventory only |
| `docs/research/specification-v0.1.md` | Machine/inventory only in completion | Path/size inventory only |
| `docs/research/webots-validation.md` | Machine/inventory only in completion | Path/size inventory only |
| `envs/__init__.py` | Machine/inventory only in completion | python_ast_parse |
| `envs/bicycle_env.py` | Focused semantic inspection | python_ast_parse |
| `envs/lqr_env.py` | Focused semantic inspection | python_ast_parse |
| `envs/path_tracking_env.py` | Focused semantic inspection | python_ast_parse |
| `envs/residual_path_env.py` | Focused semantic inspection | python_ast_parse |
| `eval_energy_efficiency.py` | Machine/inventory only in completion | python_ast_parse |
| `eval_latency_hz.py` | Machine/inventory only in completion | python_ast_parse |
| `final_real_rmse.py` | Byte-identical to inspected source | Same content as `final_test.py`; no separate reread |
| `final_test.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/.gitattributes` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/.gitignore` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/adapter.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/analyze.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/config.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/controllers/gated_validation/gated_validation.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/controllers/range_matched_validation/range_matched_validation.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/controllers/research_validation/research_validation.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/controllers/vehicle_validation/vehicle_validation.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/install-private.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/install-research.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/analyze-physical.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/calibration.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/comparison-protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/comparison.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/core.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/corridor-protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/environment-v2.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/environment.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/evaluate.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/evaluation-revision.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/final-training-protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/finalize-checkpoint.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/geometry.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/report.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision2/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/revision2/gating.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision2/native/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/revision2/native/analyze.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision2/native/protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision2/native/run.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision2/plant.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision2/protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision2/report.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision2/run.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision2/test_gate.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/README.md` | Focused semantic inspection | Path/size inventory only |
| `integrations/webots/research/revision3/audit_extension.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/confirm600.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/confirm_train.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision3/confirmation.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision3/confirmation600.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/revision3/evaluate.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/extend_train.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/extended_search.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/extension.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision3/interrupted-run.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision3/interrupted-selected-run.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision3/mapping.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision3/matched_env.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision3/native_smoke.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/pilot_env.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/pilot_search.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/pilots.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision3/protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision3/report.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/report600.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/run-training.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/revision3/test_range.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision3/train.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision4/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/revision4/bootstrap.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision4/env4.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision4/evaluation.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision4/protocol.json` | Focused semantic inspection | json_parse |
| `integrations/webots/research/revision4/report4.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision4/reserved_split.json` | Focused semantic inspection | json_parse |
| `integrations/webots/research/revision4/reward_model.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision4/run_pilots.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision4/test_contracts.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision4/train4.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision5/README.md` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/revision5/audit.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision5/bootstrap.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision5/execution.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision5/execution_env.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision5/protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision5/report.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision5/robust-protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/revision5/robust_gate.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision5/robust_run.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision5/smoke_train.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/revision5/test_execution.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision5/test_robust_gate.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/revision5/verify_robust.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/run-final-training.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/run-physical.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/run-residual-training.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/run-training.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/research/test-research.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/test-worker.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/tracking-protocol.json` | Machine/inventory only in completion | json_parse |
| `integrations/webots/research/tracking.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/train-residual.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/train-v2.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/train.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/validate-core.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/research/verify-campaign.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/research/worker.py` | Focused semantic inspection | python_ast_parse |
| `integrations/webots/run-gated-webots.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/run-research-webots.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/run-tests.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/run-webots.sh` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/runtime-sha256.txt` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/test_adapter.py` | Machine/inventory only in completion | python_ast_parse |
| `integrations/webots/worlds/research_validation.wbt` | Machine/inventory only in completion | Path/size inventory only |
| `integrations/webots/worlds/vehicle_validation.wbt` | Machine/inventory only in completion | Path/size inventory only |
| `jitter_test_results.json` | Focused semantic inspection | Path/size inventory only; ERROR: Expecting value: line 7 column 15 (char 152) |
| `lans_highway.py` | Focused semantic inspection | python_ast_parse |
| `lateral_error_model.pdf` | Inventoried; no semantic/visual review | Path/size inventory only |
| `lateral_tracking_geometry.py` | Machine/inventory only in completion | python_ast_parse |
| `lqr_jitter_test.py` | Machine/inventory only in completion | python_ast_parse |
| `measure_real_inference.py` | Byte-identical to inspected source | Same content as `benchmark_corrected.py`; no separate reread |
| `models/__init__.py` | Machine/inventory only in completion | python_ast_parse |
| `models/bicycle_model.py` | Focused semantic inspection | python_ast_parse |
| `mpc_working.py` | Machine/inventory only in completion | python_ast_parse |
| `plots/lqr_final_result.png` | Inventoried; no semantic/visual review | Path/size inventory only |
| `plots/lqr_perfected_3panel.png` | Inventoried; no semantic/visual review | Path/size inventory only |
| `plots/professional_lqr_baseline.png` | Inventoried; no semantic/visual review | Path/size inventory only |
| `proof.py` | Focused semantic inspection | python_ast_parse |
| `realistic_comparison.py` | Byte-identical to inspected source | Same content as `final_test.py`; no separate reread |
| `requirements_fixed.txt` | Machine/inventory only in completion | Path/size inventory only |
| `research-wiki/gap_map.md` | Focused semantic inspection | Path/size inventory only |
| `research-wiki/graph/edges.jsonl` | Machine/inventory only in completion | Path/size inventory only |
| `research-wiki/index.md` | Focused semantic inspection | Path/size inventory only |
| `research-wiki/log.md` | Machine/inventory only in completion | Path/size inventory only |
| `research-wiki/query_pack.md` | Focused semantic inspection | Path/size inventory only |
| `run_all_experiments.py` | Machine/inventory only in completion | python_ast_parse |
| `scenarios/__init__.py` | Machine/inventory only in completion | python_ast_parse |
| `scenarios/double_lane_change.py` | Machine/inventory only in completion | python_ast_parse |
| `setup_environment.sh` | Focused semantic inspection | Path/size inventory only |
| `simulations/__init__.py` | Machine/inventory only in completion | python_ast_parse |
| `simulations/simulate_lqr.py` | Machine/inventory only in completion | python_ast_parse |
| `test_dynamics.py` | Machine/inventory only in completion | python_ast_parse |
| `test_environment.py` | Machine/inventory only in completion | python_ast_parse |
| `test_lans_simple.py` | Machine/inventory only in completion | python_ast_parse |
| `test_latency_innovation.py` | Byte-identical to inspected source | Same content as `final_test.py`; no separate reread |
| `test_robustness_full.py` | Machine/inventory only in completion | python_ast_parse |
| `test_zero_shot_fixed.py` | Machine/inventory only in completion | python_ast_parse |
| `tests/test_controller_remediation.py` | Machine/inventory only in completion | python_ast_parse |
| `thesis_summary_table.py` | Focused semantic inspection | python_ast_parse |
| `tools/cloud/README.md` | Focused semantic inspection | Path/size inventory only |
| `tools/cloud/install-aris.sh` | Machine/inventory only in completion | Path/size inventory only |
| `tools/cloud/install-sumo.sh` | Machine/inventory only in completion | Path/size inventory only |
| `tools/cloud/install-webots.sh` | Machine/inventory only in completion | Path/size inventory only |
| `tools/cloud/install.sh` | Focused semantic inspection | Path/size inventory only |
| `tools/cloud/run-webots.sh` | Machine/inventory only in completion | Path/size inventory only |
| `tools/cloud/smoke.py` | Machine/inventory only in completion | python_ast_parse |
| `tools/cloud/sumo_smoke.py` | Machine/inventory only in completion | python_ast_parse |
| `tools/cloud/webots-demo/camera.png` | Inventoried; no semantic/visual review | Path/size inventory only |
| `tools/cloud/webots-demo/controllers/smoke/smoke.py` | Machine/inventory only in completion | python_ast_parse |
| `tools/cloud/webots-demo/result.json` | Machine/inventory only in completion | json_parse |
| `tools/cloud/webots-demo/worlds/.smoke.wbproj` | Machine/inventory only in completion | Path/size inventory only |
| `tools/cloud/webots-demo/worlds/smoke.wbt` | Machine/inventory only in completion | Path/size inventory only |
| `tools/controller_review/benchmark.py` | Focused semantic inspection | python_ast_parse |
| `tools/controller_review/compare.py` | Focused semantic inspection | python_ast_parse |
| `tools/controller_review/train.py` | Focused semantic inspection | python_ast_parse |
| `tools/controller_review/verify.py` | Machine/inventory only in completion | python_ast_parse |
| `train_curriculum.py` | Machine/inventory only in completion | python_ast_parse |
| `train_ppo.py` | Machine/inventory only in completion | python_ast_parse |
| `train_residual_ppo.py` | Machine/inventory only in completion | python_ast_parse |
| `tune_blending.py` | Machine/inventory only in completion | python_ast_parse |
| `verify_jitter_working.py` | Machine/inventory only in completion | python_ast_parse |
| `verify_numbers.py` | Focused semantic inspection | python_ast_parse |
| `verify_statistics.py` | Machine/inventory only in completion | python_ast_parse |
| `visualize_results.py` | Focused semantic inspection | python_ast_parse |
