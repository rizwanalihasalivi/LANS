# LANS: matched causal-state training and single research pipeline



27 October 2026. Evidence report; empirical failures, blocked confirmation and unavailable physical validation are retained.



## What changed and why



Previous policies were trained before the distinct-proposal recovery and packet-expiry supervisor revision. The old input interface also omitted known response/recovery history. This creates policy/controller distribution mismatch. This finite study tests a separately versioned causal state representation under matched retraining; it does not assume that more training must produce an improvement.

The causal_recovery_history_v9 interface retains 20 channels but explicitly versions three semantics: channel 14 is the known filtered-residual memory divided by 0.08; channel 15 is the EWMA of previously completed response ages divided by 0.04; channel 19 is the clipped age since the last distinct qualifying proposal divided by 0.05 (sentinel 1 if none). Channels 16 and 17 remain zero. The current request’s future inference/service/completion time is never available to the actor. Existing ABI guards refuse silent reinterpretation of old checkpoints. This is useful causal history, not proof of a fully Markov state.

Two predeclared arms use the same compensated physical inputs, controller, fresh paired optimizer/critic, initialization, training seeds and six 100,000-step endpoints (600,000 new steps). Legacy-history masks channels 14/15/19; causal-history observes them. Both use submitted-request actor credit with fixed-step GAE and all-transition critic learning. Actor loss/entropy/KL and advantage normalization use valid request samples; this changes actor/critic scaling and is disclosed. No training extension or endpoint search follows the results. Historical teacher/student/PPO training budgets are additional.

The initial policy logits are preserved by zeroing the new input columns. Old PPO and supervised-student controls also retain their logits and ignore the added history. Comparisons against the frozen student therefore include state/training adaptation effects and cannot establish pure reinforcement-learning value; the paired legacy-history arm is the corresponding feature ablation. Neither the student nor every historical baseline was retrained for this new state.

The v8 supervisor, 50ms freshness cutoff, recovery, expiry-aware continuation, actuator constraints, objective, candidate weights and margin are unchanged. Model-based input forecasting uses only completed-response history, capped at 40ms, and keeps original observation timestamps. Stale authority is zero regardless of predicted benefit. This does not compensate for delayed LQR sensing or physical actuator/communication latency. Eight new interface contracts pass; previous immutable evidence remains independently sealed.



## Frozen fresh development comparison



The initial batched actor audit found one near-tie mismatch in student_comp: a batch selected +0.08 while the single-row execution selected 0.0. Float32 logits differed by roughly 1e-7; source, inputs and recorded decisions were unchanged. The original failed verification.log and batch-replay-discrepancy.json are preserved. The corrected independent audit evaluates EVERY neural decision with the actual one-observation execution shape, still requiring exact class agreement. This is an audit correction, not a tolerance relaxation or a rerun of unfavorable episodes. Random export/golden-vector agreement is finite evidence, not bitwise equivalence of all platforms or batch shapes.



The predeclared matrix contains 1080 episodes: three actor/noise groups, 15/25m/s, two development paths, mirrored directions, nominal/tire/20ms/40ms/100ms cases and nine sources. All submitted actor outputs and causal query/history vectors, supervisor/filter/recovery decisions, physical states, actual actuator metrics and rewards were independently replayed: 1,483,380 transitions and 563,760 neural decisions. There are 192 exact 100ms/LQR trajectory matches. No reserved data were opened.



| Controller | Tracking gain vs LQR | Heading change vs LQR | Steering-rate RMS change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.000% | +0.000% | 120/120 |
| negative | -0.711% | -0.726% | -0.840% | 120/120 |
| positive | -0.711% | -0.726% | -0.840% | 120/120 |
| student_raw | +0.235% | -0.082% | +0.174% | 120/120 |
| student_comp | +0.263% | -0.099% | +0.145% | 120/120 |
| old_raw | +0.258% | -0.136% | +0.116% | 120/120 |
| old_comp | +0.284% | -0.158% | +0.086% | 120/120 |
| legacy_history | +0.188% | -0.114% | +0.015% | 120/120 |
| causal_history | +0.230% | -0.136% | -0.013% | 120/120 |



Student-relative tracking gains: legacy-history -0.076%; causal-history -0.034%. Selected arm: **None**. The unchanged criteria require at least 1% aggregate gain over LQR, both fixed corrections and the compensated student; positive student gain in every paired group; no survival loss; nominal tracking no more than 2% worse than LQR; heading and steering-rate RMS no more than 5% higher. Aggregate metrics do not imply every speed/path cell improves.



**legacy_history**: eligible=False; paired student gains: +0.1364%, -0.2176%, -0.1464%. Failed checks: lacks1% gain vs lqr; lacks1% gain vs student_comp; lacks1% gain vs negative; lacks1% gain vs positive; pair1 no student gain; pair2 no student gain.



**causal_history**: eligible=False; paired student gains: +0.1527%, -0.2090%, -0.0451%. Failed checks: lacks1% gain vs lqr; lacks1% gain vs student_comp; lacks1% gain vs negative; lacks1% gain vs positive; pair1 no student gain; pair2 no student gain.



## Original-deadline timing



The corresponding selected actor is tested when one exists; otherwise the predeclared legacy-history arm is a platform diagnostic, not a research winner. This campaign uses legacy_history, three actors, five actual worker cases and 5 seconds per case, after untimed warmup. It retains original 10ms deadlines, pinned local/helper CPUs, lower helper priority and the predeclared 1ms optional-work guard. There is one recorded campaign and no retries to erase misses.

Controller result: **0/7500 original deadlines missed**, functional checks=True, observed strict timing=True. Full replay covers 7500 ticks and 4014 issued query vectors, including past timing/recovery state. Admission decisions skipped at the budget limit: 1. Native C heartbeat: 0/3000 misses. Native heartbeat success does not validate controller timing or Webots.

admission-analysis.json describes authority and rejection reasons without changing parameters. In the causal-history nominal episodes, authority is nonzero on 5.051% of ticks, mean weight is 0.00689, and 29486/32964 ticks reject on predicted cost. At 40ms only 217 ticks are active (0.658%). Limited admitted authority bounds how much the policy can influence tracking; these descriptive results do not prove that relaxing safety/freshness checks would be appropriate. Added causal history did not establish the required performance headroom.

deadline-attribution.json retains every miss, including release lateness, elapsed processing, thread CPU, sensing/LQR and feature work. The components may overlap and are not a proof of a unique root cause. Optional work cannot recover a deadline already lost to scheduling or mandatory processing. A finite zero-miss observation, if achieved, is not a hard real-time/WCET certificate. The fixed-step plant advances during software ticks; survival does not establish continuous-time physical safety during a host pause. Cross-version timing campaigns ran under different conditions and cannot prove a causal speedup.



## Laptop package and external evidence



The new Python 3.10 ZIP contains all three frozen actors, explicit ABI/hash checks, Windows/macOS launchers, the full raw replay and no Torch dependency. The clean minimal-environment packaging smoke completed 750 ticks, with 0 misses and fallback=True. Its half-second cases are packaging diagnostics, not strict qualification or actual laptop results. Nominal learned assistance was not observed in every seed during this short smoke; that is reported separately from fallback and timing.

On the actual laptop, extract LANS_Causal_Python310_Kit.zip, then run RUN_WINDOWS.cmd or `bash RUN_MAC.command`. This performs five 13-second cases per actor (195 measured seconds plus warmup), verifies the bundle before execution and produces laptop-results/Results.zip. Preserve failures. Import with the same pipeline command plus `--laptop-results /path/to/Results.zip`. The importer accepts data files only, validates the matching source/model bundle and independently replays 19,500 expected ticks. Participant data are not cryptographic hardware attestation.



## One command and honest stage status



From the repository root using the Python3.10 research environment:



```bash

python tools/controller_review/run_single_pipeline.py --publish

```



The command verifies old evidence; resumes the fixed six-training/1,080-episode protocol; executes timing once; replays raw data; builds and clean-tests the target kit; imports target data when supplied; seals evidence; creates editable Word/PDF reports; and optionally commits/pushes this branch. Completed stage outputs are retained. Partial runs are not silently overwritten. Exit 2 means at least one scientific/external requirement remains unmet, while exit 1 is an execution error. A successful file-generation stage never overrides an empirical failure.



| Requirement | Current status |
|---|---|
| pipeline_contracts | passed |
| prior_evidence | passed |
| matched_development | passed |
| admission_analysis | passed |
| scientific_selection | failed_requirement |
| timing | passed |
| timing_replay | passed |
| strict_original_10ms | passed |
| portable_kit | passed |
| portable_kit_audit | passed |
| packaging_smoke | passed |
| actual_laptop | awaiting_external_run |
| reserved_unseen | blocked |
| native_webots | blocked |
| robust_vehicle_baseline | needs_research |
| primary_references | awaiting_primary_source_verification |
| physical_validation | not_performed |
| submission | draft_only |
| evidence_seal | passed |
| evidence_report | generated (this document) |



Reserved/unseen-path evaluation and current-ABI native Webots confirmation remain gated on scientific selection plus corresponding-controller timing. If those gates pass later, confirmation still needs its declared protocol and current-controller integration; this orchestrator does not call the old student adapter and label it a new confirmation.

A full robust vehicle safety-filter reproduction still requires justified vehicle uncertainty bounds, terminal safe set/backup, primary algorithm details and a matched evaluation. The existing verified scalar specialization is not that reproduction. Thirty-two references have structural checks and five uploaded primary versions are verified; the remaining primary-source/novelty audit is open. These research tasks cannot be passed by generating a stub.

No physical sensor, communication or actuator evidence is available. Vehicle-readiness, global convergence, universal neuro-symbolic novelty, 49-fold speedup and measured energy superiority are excluded. A separately passing one-second worker recovery test from v8 does not cancel any current timing miss or prove improved tracking. Paper1 remains the residual LQR/PPO/supervisor architecture; V2V is excluded.

These are reviewable evidence reports, not a submission-ready claim that unresolved requirements passed. Failures must motivate a justified new protocol or narrower claims, never relaxed thresholds or repeatedly reopening development outcomes until a score crosses a line.
