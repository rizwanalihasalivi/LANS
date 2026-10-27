# LANS bounded recovery, packet-expiry prediction and deadline guard



27 October 2026 (Asia/Shanghai). Verified experimental revision; failed scientific and timing criteria remain failures.



## Implemented corrections



The previous 40 ms case could not finish three control-tick recovery checks before its packet became stale. The revised supervisor requires three DISTINCT valid, fresh and predictively beneficial proposal sequences. Reusing one held packet cannot manufacture three recovery confirmations. Internal filter/evidence memory may survive a short stale gap only within 50 ms of the last distinct qualifying decision. Every stale tick immediately has ZERO learned authority. Missing/invalid inputs, cost rejection, evidence expiry and local budget failure reset recovery. The original 50 ms stale cutoff is unchanged.

The 50 ms liveness limit bounds each gap between distinct qualifying decisions, not the total span of all three responses. Preserved filter state is internal controller history, not an active stale command. A fresh qualifying packet and current-state predictive check remain necessary for nonzero weight; no old observation is retimestamped or resubmitted as fresh.

The nominal predictor now applies assistance only over the CURRENT packet’s remaining eligible control ticks, then follows LQR continuation. It no longer forecasts that assistance persists for the full 1 second without another valid packet. Baseline and candidate use the same current state, actuator dynamics, path preview,100-step horizon, cost weights and margin. Full 100 step and zero-assistance numerical limits match the previous kernel. Recovery and expiry-continuation were revised jointly; this study does not isolate their individual performance effects.

$$n_t=\max\!\left(0,\left\lceil\frac{a_{\max}-a_t}{h}\right\rceil\right),\qquad a_{\max}=0.05\ \mathrm{s},\quad h=0.01\ \mathrm{s}.$$

The experimental v7 policy-input forecast is unchanged: completed-response history only, no future completion/service information,40 ms horizon cap, latest-state admission and original timestamps. Residual filtering, cap 0.25, ramp 0.05, steering limits and physical reward are unchanged. No new training or hyperparameter search occurred. Frozen policies were not trained for this revised gate; input/controller distribution shift is a remaining limitation.

A separate optional deadline guard suppresses new forecast/query work near the original deadline and skips predictive admission when less than 1 ms remains. It uses prepared LQR fallback and resets learned recovery. The reserve is a predeclared heuristic, not WCET proof; mandatory sensing/LQR still runs, and original deadlines never shift. A cycle already late remains a miss.



## Fresh full development matrix



Eight mechanism contracts pass. NumPy student exports match Torch classes on 2,000 test vectors per actor, and PPO exports retain the original weight hashes. The seven methods share the revised supervisor, sensing, noise, actuator, delay and available-information rules. Raw/compensated PPO are compared with matching raw/compensated students and both fixed corrections. The frozen grid covers 15/25 m/s, two known paths, mirrored directions, three actor/noise groups and nominal/tire/20 ms/40 ms/100 ms cases.

All **840 episodes survived**. Exact replay checked **1,153,740 transitions**, **375,840 actor decisions**, all raw/forecast inputs, history, physical trajectories, gate decisions, rewards and metrics. All **144** severe-delay/LQR trajectory pairs match exactly. Typed NumPy traces preserve values and avoid lossy CSV parsing.



| Controller | Tracking gain vs LQR | Heading change | Rate RMS change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.000% | +0.000% | 120/120 |
| negative | -0.734% | -0.730% | -0.869% | 120/120 |
| positive | -0.734% | -0.730% | -0.869% | 120/120 |
| student_raw | +0.257% | -0.111% | -0.013% | 120/120 |
| ppo_raw | +0.228% | -0.106% | +0.090% | 120/120 |
| student_comp | +0.272% | -0.123% | -0.038% | 120/120 |
| ppo_comp | +0.295% | -0.153% | +0.041% | 120/120 |



PPO student-relative gains: raw **-0.029%**, compensated **+0.024%**. Neither meets the unchanged 1% requirement; the compensated arm also misses 1% over LQR and has a negative paired group. Selected controller: **None**. All exact failed criteria are retained in decision.json.

At 40 ms, raw PPO has **278** active ticks and compensated PPO **294**. The structural recovery blockage is removed, while every stale tick remains baseline-only. Actual admission still requires predicted benefit; the favorable-cost unit test alone is not a performance claim.

These are new controller rules and a fresh expanded development grid. Do not interpret their aggregate difference from older 2–3% campaigns as a paired causal effect of one change. The earlier measured trajectories remain preserved; no prior failure or success is overwritten. The current result does not establish PPO superiority and does not justify further unplanned tuning until a score passes.



## Original 10 ms timing and environment



| Guard | Controller ticks | Original deadline misses | Functional fallback | Strict observed timing |
|---|---:|---:|---|---|
| off | 7500 | 2 | True | False |
| on | 7500 | 1 | True | False |



Native C heartbeat: **0/3000 misses**. The randomized per-seed guard order, full warmup, pinned control/helper CPUs and lower helper priority were fixed before outcomes. Timing ran after offline research jobs exited. Replay verified 15000 controller ticks,3000 heartbeat ticks and 8028 recorded query vectors;2 predictive decisions were skipped by the guard. Raw queries that never returned lack an independently recorded sent vector; this limitation is stated rather than hidden.

The guard-on miss occurred after roughly 9.425 ms release lateness followed by roughly 9.329 ms mandatory sensing/LQR work. Optional work was skipped, but the lost budget could not be recovered. This demonstrates the remaining sensing/scheduling requirement. Original timestamps and stale/late authority rejection pass; strict 10 ms execution still fails.

Two versus one misses is a finite A/B observation, not statistically established superiority or a hard-real-time guarantee. Earlier 657/7,500 and 164/1,500 campaigns used different revisions/windows/environments. Their apparent difference cannot be attributed solely to this guard. The current cgroup reports zero throttling during the recorded interval; post-campaign platform metadata is preserved and is not backfilled into historical runs. LQR, observer and supervisor still share the local process; software commit timestamps are not actuator timestamps.

A separate fixed dynamic-recovery diagnostic exercised actual one-second PPO-worker waits for requests observed in [2,3)seconds, followed by healthy responses. All three seeds had nonzero assistance before and after the stall, actual delayed packets were rejected, and fallback checks passed: functional recovery **True**, **0/2400 misses** in this separate 8 second-per-seed run. This does not erase the guard-A/B miss. The dynamic audit verifies packet timing, actor outputs and physical trajectories; complete query/gate-memory replay is recorded separately for the 15,000 tick A/B campaign.

The clean Python 3.10 kit smoke recorded 750 ticks,0 misses and functional fallback True. It is a packaging diagnostic, not actual laptop, Webots or physical validation. The kit runs all three actors across five 13 second cases, verifies raw outputs automatically and creates laptop-results/Results.zip.



## What remains and why



- Scientific selection remains FAILED. A new matched policy/objective study would require a justified finite protocol and evidence of additional headroom; another training run cannot be promised to beat a strong student.

- Strict 10 ms response remains FAILED. Target-specific bounded sensing/control execution and scheduling validation are needed. The user laptop has not been remotely executed; run the extracted RUN_WINDOWS.cmd or `bash RUN_MAC.command` and return laptop-results/Results.zip.

- Reserved/unseen-path and corresponding-controller native Webots confirmation remain UNOPENED because the promotion gates fail. Older native interface checks are not confirmation of this revision.

- Full matched robust VEHICLE-controller reproduction remains incomplete. The previously verified scalar Algorithm 2 contract does not provide the nonlinear vehicle confidence/error set, terminal safe set, noisy-state certificate or original-author numerical reproduction. The existing nominal vehicle specialization remains explicitly limited.

- All 32 original references have a structural audit and five uploaded primary sources are version-verified. Remaining primary metadata/claim verification and broader novelty justification are open. GitHub primary-code search returned Forbidden in this environment; no unavailable source was invented.

- Physical sensor, communication and actuator validation requires connected hardware if vehicle readiness is claimed. Current scope is software-in-the-loop; no physical readiness, global stability, energy advantage, universal neuro-symbolic novelty or 49-fold speedup is asserted.

- Evidence reports and reviewer-status records are reviewable drafts, not a submission-ready superiority/safety paper. No V2V mechanism was introduced into Paper 1.



Resume verified software stages with `python tools/controller_review/run_recovery_work.py --publish`. This command preserves partial/failed runs, original deadlines and frozen criteria; it cannot manufacture laptop or vehicle measurements.
