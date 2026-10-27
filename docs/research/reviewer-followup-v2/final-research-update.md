# LANS reviewer follow-up: verified development evidence

27 October 2026 (Asia/Shanghai). Architecture: fresh-state LQR baseline plus causal PPO residual, freshness rejection, and supervisory authority. This is not full-command PPO/LQR switching. Prior failed experiments remain unchanged in reviewer-causal-v1. This document is a research update, not a declaration of submission or vehicle readiness.

## What was completed

- Frozen 864-episode follow-up: 3 paired PPO/student seeds, 20 m/s, 2 development paths, exact left/right mirrors, 4 conditions, 18 methods. All 864/864 episodes survived. Fresh development noise; no new training or outcome-driven tuning.
- Independently recomputed raw metrics, causal low-pass recurrence, actuator bounds, fusion and 204 exact severe-delay/LQR trajectory pairs.
- Replayed 202800 PPO and 162240 submitted queries from recorded observations; zero action disagreements. All frozen input hashes and removed future/oracle channels checked.
- Added same-profile student and both fixed±0.04 rad controls to separate PPO learning from supervisory gain/filter effects.
- Implemented a disclosed nominal specialization of Wabersich–Zeilinger Eq 5/Algorithm 1; complete solver failures and fallback counts retained.
- Ran predeclared randomized timer A/B with original 10 ms deadlines, actual PPO worker, observer/LQR, partitioned generated worker contention and lower worker priorities. Independently replayed raw plant/observer/model/timestamps.
- Packaged full-controller Python 3.10 laptop SIL kit with portable NumPy PPO, five fault cases, raw CSVs, independent verifier and Windows/macOS launchers. Clean minimal Linux dependency environment smoke-tested; actual target OS execution pending.

## Matched development results

Gains are averages of episode RMSE on this fresh development grid. These are not confidence bounds or unseen-test generalization. Different grids cannot be compared as paired improvements. Steering column is actuator-rate RMS relative to matched LQR.

| Method | Tracking gain vs LQR | Heading change vs LQR | Steering-rate change vs LQR | Survival |
|---|---: |---: |---: |---: |
| LQR | +0.000% | +0.00% | +0.00% | 48/48 |
| Age gain, −0.04 | -32.364% | +0.44% | +0.10% | 48/48 |
| Age gain, +0.04 | -32.364% | +0.44% | +0.10% | 48/48 |
| Age gain, student | +8.114% | -0.85% | +84.24% | 48/48 |
| Age gain, PPO | +7.685% | -0.85% | +83.30% | 48/48 |
| Filtered, −0.04 | -9.973% | +0.10% | +0.10% | 48/48 |
| Filtered, +0.04 | -9.973% | +0.10% | +0.10% | 48/48 |
| Filtered, student | +6.116% | -2.32% | +27.79% | 48/48 |
| Filtered, PPO | +5.789% | -2.38% | +27.48% | 48/48 |
| Predictive, −0.04 | -2.743% | +1.58% | +0.45% | 48/48 |
| Predictive, +0.04 | -2.743% | +1.58% | +0.45% | 48/48 |
| Predictive, student | -0.000% | +0.00% | -0.01% | 48/48 |
| Predictive, PPO | -0.001% | +0.00% | -0.01% | 48/48 |
| Preview, −0.04 | -0.917% | -0.26% | -0.59% | 48/48 |
| Preview, +0.04 | -0.917% | -0.26% | -0.59% | 48/48 |
| Preview, student | +0.685% | -0.42% | +0.47% | 48/48 |
| Preview, PPO | +0.728% | -0.45% | +0.38% | 48/48 |
| Nominal PSF, PPO | +6.450% | -1.26% | +101.97% | 48/48 |

Labels: Age gain = age_original; Filtered = age_filtered; Predictive = predictive_filtered; Preview = preview_filtered. Signed numbers identify fixed residual proposals in radians. Student and PPO use identical profile settings.

## Diagnosis and selection

The original age-gain PPO improves lateral tracking but strongly increases steering activity. The predefined 0.1 s low-pass and 0.25 authority cap reduce that activity, while still failing the 5% steering trade-off criterion. The same-gain supervised student remains better than PPO in mean lateral RMSE, including two of three paired seeds for age_filtered. Thus the additional value of PPO fine-tuning is not established.
Replacing raw command-jump cost with predicted physical actuator-rate cost alone admits almost no useful assistance. Observable curvature preview recovers a small tracking gain with modest heading/rate changes, but remains below the frozen 1% tracking-gain threshold and does not consistently beat the student. This local 20-step model/objective remains a bottleneck; these results do not isolate a single causal reason or prove a new cost will succeed.

| Profile/source | Applied nonzero-weight ticks / total |
|---|---: |
| LQR | 0/62400 |
| Age gain, −0.04 | 46776/62400 |
| Age gain, +0.04 | 46776/62400 |
| Age gain, student | 46776/62400 |
| Age gain, PPO | 46776/62400 |
| Filtered, −0.04 | 46776/62400 |
| Filtered, +0.04 | 46776/62400 |
| Filtered, student | 46776/62400 |
| Filtered, PPO | 46776/62400 |
| Predictive, −0.04 | 3947/62400 |
| Predictive, +0.04 | 3947/62400 |
| Predictive, student | 111/62400 |
| Predictive, PPO | 97/62400 |
| Preview, −0.04 | 5100/62400 |
| Preview, +0.04 | 5100/62400 |
| Preview, student | 2693/62400 |
| Preview, PPO | 2875/62400 |
| Nominal PSF, PPO | 44982/62400 |

Eligibility requires at least 1% gain over LQR, same-profile student and both constants; positive student-relative gains for all three seeds; no survival loss; nominal no more than 2% worse than LQR; heading and rate no more than 5% worse than LQR.

**Selected profile: None. Reserved confirmation remains unopened.** No criteria were relaxed after seeing results. No further training, native winner confirmation or unseen-path claim is justified by this screen.

## Published-method comparison and claim boundary

Primary source: Wabersich and Zeilinger, arXiv: 1812.05506v4, §4.1 Eq 5 and Algorithm 1, supplied by the author. The nominal quadratic program minimizes first-command deviation from the learned proposal, respects disclosed model-state/input limits, and uses a constant-curvature terminal equilibrium with shrinking-horizon recovery. The same noisy observer, nonlinear software plant, actuator limits, paths and delay cases were used for the matched experiment.
This is a nominal linear specialization, not the authors’ implementation or a reproduction of their uncertainty-aware Algorithm 2. Exact-model, state-knowledge and constant-curvature assumptions do not hold on this test plant. Consequently the paper’s safety theorem cannot be transferred. If the full and shortened programs fail, the fresh-state LQR fallback is explicitly uncertified. Do not interpret this comparison as superiority over the complete published method.

Nominal PSF handled 46776 command requests and logged 1794 uncertified LQR fallback events. A request may solve both full and shortened programs. Its tracking gain is 6.450%; its actuator-rate change is 101.97%.
Closest related areas remain predictive safety filtering, Simplex/runtime assurance, delayed-observation shielding and delay-aware MPC. LANS cannot claim novelty merely from combining LQR, PPO and thresholds or naming a supervisor neuro-symbolic. Explicit predicates and predictions are implemented engineering mechanisms; a broad claim of unique symbolic reasoning or formal safety is unsupported. Supplied primary texts support the scoped comparison; full venue/DOI/reference-list verification and an authors-code matched benchmark remain incomplete.

## Original-deadline timing A/B

| Timer profile | Missed 10 ms deadlines | Functional replay | Nonzero correction ticks |
|---|---: |---|---: |
| sleep | 687/6000 | True | 2022 |
| absolute | 305/6000 | True | 2350 |

Both profiles use the predefined age_filtered residual diagnostic and old 25 k PPO exports. Parent runs on one core; worker/nice 10 and two generated stressors/nice 19 run on the other. Native profile uses CLOCK_MONOTONIC absolute sleep plus at most 100 µs spin, preserving every original target and 10 ms deadline. Same noise per seed and randomized profile order. No OS isolation, privileged real-time scheduling or host contention exclusion exists.
**Any observed miss fails strict timing.** Finite zero misses would establish only observed timing in this setting, not WCET. Fixed-step plant survival and functional LQR fallback do not prove continuously evolving real-time plant safety during host stalls. No 100 Hz or vehicle-readiness guarantee is made.

## Reviewer-by-reviewer correction status

| Comment | Evidence / remaining limit |
|---|---|
|1 Novelty / neuro-symbolic | Explicit predicates and predictor specified; no first-of-kind or formal symbolic novelty claim |
|2 Latency reward | Previous causal PPO pilots removed exogenous latency penalties; this follow-up changes no training reward |
|3 Delay implementation | One-in-flight queues and real worker unavailability use original observation timestamps; plant/service versus physical timing separated |
|4 LQR delay contradiction | Fresh local LQR is distinct from stalled PPO; no 1000 ms delayed-feedback LQR tolerance claim |
|5 49-fold speedup | Withdrawn; matched actor distributions in reviewer-causal-v1, no simulation-period inference denominator |
|6 Ablation frequency | Per-query inference and complete-loop timestamps retained; no assumed frequency from reward removal |
|7 Nominal degradation | Same-gain constants/student and LQR compared; failed PPO promotion and all trade-offs retained |
|8 Generalization | Mirrored fresh-development noise only; reserved/unseen tests not opened on failed screen |
|9 Stability proof | No global/asymptotic convergence or safety certificate; clipping, slew limits, bounded residual are not a proof |
|10 Missing details | Frozen protocols, 3 paired seeds, reward equations, categorical distribution, thresholds, model/source hashes and raw traces supplied |
|11 Energy/blind distance | Unsupported comparisons withdrawn; physical sensing-to-actuation/energy measurement remains unavailable |
|12 Numerical/citation consistency | Raw metrics, query replay, export verification and source-version literature checked; complete publisher bibliography verification remains |

See reviewer-causal-v1/original-claim-audit.md, stability-claim-boundaries.md, literature-positioning.md and reviewer-response.md for the unchanged original review mapping. This follow-up does not silently replace its failed experiments.

## What remains and why

| Work item | Status |
|---|---|
| Gate/objective mismatch investigation | Completed fixed follow-up; useful balanced PPO winner not established |
| Learning additional value | Tested with same-gain controls; not established |
| Local 10 ms requirement | See raw A/B table; unresolved if any miss; no hard-real-time guarantee |
| Reserved/unseen confirmation | Intentionally not opened because development screen failed |
| Published comparison | Nominal Eq 5/Algorithm 1 specialization complete; robust authors-code reproduction and full bibliographic metadata verification remain |
| Laptop rerun | Full-controller kit ready and Linux smoke verified; actual Windows/macOS data required |
| Physical sensor/communication/actuator validation | Requires connected target hardware/vehicle; unavailable in this cloud |
| Paper/report | Evidence update complete; positive-performance submission claims still unsupported |

Next research decision: either report the engineering/failure-analysis study honestly, or freeze a new teacher-headroom/learning objective study before new training. Repeatedly tuning this development grid cannot replace untouched confirmation. Hardware validation requires the user to run the kit and return results; physical readiness additionally requires actual sensors, communications and actuators.

## Reproduction and artifacts

`python tools/controller_review/run_followup_work.py --publish` resumes completed stages, runs outstanding frozen software stages, verifies outputs and pushes milestones. It never executes the user laptop, opens reserved tests on failure, trains new policies or marks physical validation complete.

See summary.json, decision.json, actor-verification.json, episodes.csv and raw pair-*/traces. Timing source/protocol/raw traces and verification are under timing/. The full laptop ZIP and kit-smoke/ raw verification are included. Original reviewer-causal-v1 evidence is preserved.
