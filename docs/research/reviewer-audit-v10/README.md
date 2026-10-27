# LANS active-path audit and 20% feasibility



27 October 2026. New target: at least 20% lower mean penalized episode lateral RMSE than every declared matched baseline, while preserving survival and the existing heading/smoothness limits. It is a research target, not a guarantee. Previous frozen 1% criteria and historical outcomes remain unchanged.



## Verified fixes



1. **Time-limit bootstrap observation:** the inherited environment returned the pre-transition observation when it reached the horizon. Gymnasium/SB3 bootstraps from terminal_observation on truncation, so the critic received a stale terminal input. The new environment senses the next state before returning the terminal observation. Nonterminal reward/transition/input parity with the old numerical core is tested. This is a real learning-interface defect; its existence does not prove it caused the previous low gains. No retraining effect is claimed by a frozen-policy diagnostic.

2. **Packet identity and request validity:** nonfinite/fractional/bool identifiers, malformed packets, same-ID timestamp/residual mutation, negative/nonfinite service/time and out-of-bound proposed residuals are rejected. Previously a NaN ID could retain authority under a favorable predictor, and NaN service created an undeliverable pending request. Invalid baseline commands raise an explicit control-system fault instead of returning NaN as fallback; speed/actuator numerical-domain violations revoke assistance. These defects are demonstrated by before/after contracts. Their fix hardens correctness and does not itself establish a tracking gain. Physical fail-operational handling of invalid sensing/LQR remains outside this SIL evidence.

3. **Nominal predictor discretization and rate accounting:** the old 10ms predictor updates actuator position before evaluating the bicycle derivative and charges the initial instantaneous actuator rate; the plant/reward use continuously integrated actuator motion and its average change over the tick. The new isolated model integrates the SAME nominal linear bicycle/actuator with 1ms RK4 and charges the average tick rate. It does not use the hidden nonlinear plant friction/stiffness, future noise or future policy actions. All weights, cap0.25, filter0.3s, ramp0.05, 50ms freshness, benefit margin and distinct-proposal recovery remain unchanged. Numerical integration and rate accounting changed jointly, so this study does not isolate them.

4. **Runtime checks:** the new audited_history_comp_v10 runtime enforces strict response ID types and uses the hardened numerical supervisor. Its actor input ABI remains causal_recovery_history_v9 because input semantics are unchanged. Old v8/v9 code, kits and evidence remain immutable historical revisions; use the new runtime for these fixes. The corrected Env is the entry point for future declared retraining, not a silent patch to historical training.



**36 contracts pass:** 16 new contracts plus submitted-credit, recovery and causal-interface regressions. Repository inventory checks 2625 tracked/new Python files (1124 historical snapshots) for hashes/AST validity. Detailed semantic coverage is explicitly listed in inventory.json: active PPO preprocessing/action/credit/reward/observation, packet/recovery/forecast/fusion, sensing/plant/LQR, metrics/baselines and orchestration plus new modules. Static inventory is not a claim of manual semantic review of every historical file. Syntax errors: 0; see the inventory for scope.



## Independent numerical validation



The nominal RK4 objective matches an independently coded SciPy DOP853 reference on 4 full-horizon cases; maximum absolute objective error is 6.34e-08. On 100 fixed random nominal states, old/new objective relative discrepancy has median 4.310% and p95 17.215%; admission classifications differ on 0/100. Cost discrepancy alone does not prove more useful assistance or better real-plant prediction. Warm scalar kernel median 63.7us, maximum 289.6us in this diagnostic; this is not WCET or complete-controller timing.



## Fresh matched diagnostic



The fixed grid contains 360 fresh episodes: three frozen actor/noise groups, 15/25m/s, two known paths with exact left/right mirrors, nominal/tire/20ms cases and five sources. Four primary sources share the new numerical supervisor; ppo_euler is a labeled previous-numerics mechanism control. All physical and policy inputs, packet/recovery decisions, rewards and metrics replay over 494,460 transitions and 247,248 neural decisions. Planner proposals are independently regenerated from available information.



| Source | Gain vs LQR | Heading change | Steering-rate RMS change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.000% | +0.000% | 72/72 |
| student_rk | +0.537% | -0.231% | +0.182% | 72/72 |
| ppo_rk | +0.379% | -0.211% | +0.195% | 72/72 |
| planner_rk | +1.488% | -1.883% | -3.254% | 72/72 |
| ppo_euler | +0.174% | -0.062% | +0.070% | 72/72 |



New PPO target gains by comparator: {'lqr': 0.3785601231417024, 'student_rk': -0.15917848389164213, 'planner_rk': -1.12594453551631, 'ppo_euler': 0.20470566053629735}. Diagnostic 20% pass: **False**. Causal same-authority planner has balanced 20% headroom vs LQR/student: **False**. No final controller promotion is allowed from this narrow diagnostic.

The planner is a strong nonlearned comparator, not an oracle: it uses only estimated state, measured actuator/speed, current reference preview and EWMA of completed response history. It forecasts nominal LQR continuation to the expected response time and compares the five proposed residuals, including zero, under the same gate. Future held-packet behavior is approximate; the true current-state gate still decides at actual arrival. It has additional planning computation, recorded in each trace, and has not earned a real-time deployment claim.

A causal planner failing this headroom screen does not mathematically bound every possible PPO or controller. It does mean this finite study has not supplied evidence that another blind training run can achieve 20%. No new training runs, extensions, weaker baselines or post-hoc threshold changes occur. A promising screen would require a separately frozen finite training protocol before execution. Current numerical-policy distribution shift remains a limitation.



## Why previous PPO contribution was small



The previous full v9 audit found nonzero authority on only 5.05% of nominal causal-PPO ticks, with mean weight0.00689; most ticks rejected on predicted cost, 40ms assistance was rarer and 100ms assistance was zero. The current .08rad residual bound and .25 weight cap bound the added command to .02rad even before filtering/recovery. A 0.3s filter, repeated beneficial-packet recovery and a 0.1% improvement margin on a 1s prediction reduce effective control authority. These are design restrictions, not all coding errors, and removing them would change the assurance/performance trade-off rather than constitute a harmless bug fix.

The reward explicitly trades lateral accuracy against heading and actual actuator-rate RMS. It cannot guarantee a tracking-only 20% gain while every other metric also improves. Submitted-request credit removes ignored actor actions, but sparse authority, delayed rewards, partial state information and actor/critic loss scaling remain optimization limitations. A three-seed fixed finite budget is not a proof of global policy optimality. Reference-preview/coarse nominal-model mismatch and unvalidated uncertainty bounds remain research issues.

If all packets are stale and the declared architecture enforces exact fresh-state LQR fallback, improving on LQR by20% in that same stale-only condition is impossible: commands/trajectories are identical. Overall mixed-condition targets are different and must retain their declared weights. Do not remove severe-delay cases or weaken LQR to manufacture a headline result.



## New-runtime integration smoke



The new runtime completed 1500 original 10ms ticks with **1 misses**, functional fallback=True. Full raw replay verifies 1500 ticks and 806 issued inputs/history vectors. This is three actors x five actual worker cases x one second after warmup, not full timing qualification, native Webots or actual laptop evidence. These current-model results do not inherit the older v9 0/7500 claim, and any misses are retained.



## Run and remaining work



```bash

python tools/reviewer_v10/run10.py --publish

```



The single resumable audit pipeline checks tests, nominal numerical accuracy, source inventory, fixed matched episodes, full replay, new-runtime smoke and report/seals, then optionally commits/pushes this branch. Exit2 records an unmet20% diagnostic target; partial runs are preserved. It does not silently overwrite old source/evidence or run reserved data.

Remaining before any20% superiority claim: a learned controller passing the NEW target against the strongest matched nonlearned controls; independent broader speeds/paths/noise/training seeds and all declared baselines; a full matched robust published-controller reproduction; corresponding-controller timing on the actual laptop; reserved/native Webots confirmation after selection; and primary-reference/novelty verification. Physical sensor, communication and actuator tests are necessary for vehicle-readiness claims. Current evidence remains SIL and no deployment, global stability, energy or49-fold speedup claim is made.
