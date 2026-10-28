# LANS: actual PPO training after the audit fixes



27 October2026. The user explicitly requested training after the failed causal-planner headroom diagnostic. This new finite protocol proceeds despite that heuristic failure; historical outcomes and criteria remain unchanged. The20% target is measured, not guaranteed.



## What was actually trained



Three new RNG seeds continue the corresponding previous causal-history PPO checkpoints for exactly100,000 additional environment steps each:300,000 NEW steps total. Actor, critic, Adam optimizer and reward-normalization statistics are retained; source preservation is contract-tested and initial checkpoints/normalizers are saved. The rollout buffer/environment/RNG are fresh. Original supervised and previous PPO training budgets are additional. Only the three final endpoints are compared: no best-checkpoint cherry-picking, per-seed mixing or post-result extensions.

Training uses the corrected v10 terminal next-observation interface, strict packet/identity checks and nominal RK4 predictor with average actual actuator-rate cost. Source/model input dependencies are pinned to the prior immutable evidence. The causal20-channel input ABI, physical reward, submitted-request actor credit, fixed-step GAE, all-transition critic,50ms stale cutoff, residual bound0.08rad, filter0.3s, cap0.25, recovery/ramp/margin and actuator limits remain unchanged. No future response/service information is provided to the actor.

The training distribution covers15/20/25m/s, two known paths, exactmirrors and nominal/tire/20/40/100ms conditions. Its noise namespace is new and separate from the fresh development namespace. Severe-delay transitions can have zero policy authority; they are retained rather than removed to inflate tracking gains. No reserved path is opened.



| Pair | New RNG seed | Additional steps | Submitted requests | Active assistance ticks | Wall seconds |
|---|---:|---:|---:|---:|---:|
| 0 | 7701 | 100000 | 55471 | 2978 | 68.0 |
| 1 | 7802 | 100000 | 59045 | 2709 | 68.7 |
| 2 | 7903 | 100000 | 52861 | 3996 | 63.7 |



## Fresh matched evaluation



The predeclared full development grid has 840 episodes:15/25m/s x2knownpaths x2mirrors x5scenarios x7sources x3actor/noise groups. Every source uses the same corrected supervisor, sensing, actuator limits and matched exogenous conditions. Student and oldPPO weights remain frozen; the newPPO is the continued endpoint. The causal nominal planner and both fixed corrections are nonlearned controls. A full robust published vehicle baseline/MPC is not included, so superiority over all published controllers cannot be claimed.

Independent single-observation inference and full input/history/compensation/packet/recovery/physical/reward replay verify 1,153,740 transitions and 281,880 neural decisions. Planner proposals are independently regenerated from available information; 144 severe-delay/LQR trajectory pairs match exactly. All input source/model hashes and exports are checked.



| Source | Tracking gain vs LQR | Heading change | Steering-rate RMS change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.000% | +0.000% | 120/120 |
| negative | -0.591% | -1.247% | -1.075% | 120/120 |
| positive | -0.591% | -1.247% | -1.075% | 120/120 |
| student_rk | +0.429% | -0.167% | +0.143% | 120/120 |
| oldppo_rk | +0.360% | -0.196% | +0.036% | 120/120 |
| planner_rk | +1.025% | -1.167% | -2.182% | 120/120 |
| newppo_rk | +0.098% | -0.223% | -0.074% | 120/120 |



## New PPO contribution and20% target



- NewPPO tracking gain vs lqr: **+0.0976%**.

- NewPPO tracking gain vs negative: **+0.6846%**.

- NewPPO tracking gain vs positive: **+0.6846%**.

- NewPPO tracking gain vs student_rk: **-0.3328%**.

- NewPPO tracking gain vs oldppo_rk: **-0.2630%**.

- NewPPO tracking gain vs planner_rk: **-0.9373%**.



20% development screen: **False**. Failed checks: less_than20pct_vs_lqr; nonpositive_pair2_vs_lqr; less_than20pct_vs_negative; less_than20pct_vs_positive; less_than20pct_vs_student_rk; nonpositive_pair0_vs_student_rk; nonpositive_pair1_vs_student_rk; nonpositive_pair2_vs_student_rk; less_than20pct_vs_oldppo_rk; nonpositive_pair0_vs_oldppo_rk; nonpositive_pair2_vs_oldppo_rk; less_than20pct_vs_planner_rk; nonpositive_pair0_vs_planner_rk; nonpositive_pair1_vs_planner_rk; nonpositive_pair2_vs_planner_rk.

The screen requires at least20% lower mean penalized episode tracking RMSE than EVERY listed comparator, positive paired gain in all three groups, no survival loss, nominal tracking no more than2% worse than LQR and overall heading/actuator-rate RMS no more than5% higher. Exact ratio comparisons avoid floating-point misclassification at the20% boundary. Aggregate metrics do not guarantee every individual speed/path cell improves.

The matched old/new PPO comparison measures the result of additional training under the corrected environment. It does not isolate the individual causal effects of terminal-observation repair, predictor integration, continued optimizer/reward statistics or RNG changes. Prior0.379%/1.488% diagnostic values came from a narrower grid with other noise; do not compare those aggregates as if only training changed.

Limited authority, sparse accepted proposals and a strong LQR/student/planner remain structural constraints. A failed target is not converted into a pass by deleting delayed conditions, weakening baselines, extending training until a score crosses a line or choosing different best seeds. No universal impossibility claim follows from this finite study.



## Timing, confirmation and scope



Winner-specific original-deadline timing is conditional on the20% selection screen. If the screen fails, no current-model timing success is claimed. Previous v9 zero-miss timing and the v10 one-miss smoke are historical experiments, not certification of these new actors. All reserved/native Webots confirmation, actual laptop execution and physical sensor/communication/actuator validation remain separate evidence requirements. No deployment, global stability, universal novelty, energy or49-fold speedup claim is made.



## Resume



```bash

python tools/reviewer_v11/run11.py --publish

```



The command checks provenance/contracts, continues the three finite runs, exports actors, executes the fixed matched matrix, independently replays raw data, seals evidence and builds Word/PDF reports. Completed and partial outputs are preserved. Exit2 means the20% empirical requirement remains unmet. No further training starts automatically.
