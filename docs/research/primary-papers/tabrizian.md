# Primary-source review: Tabrizian et al., DAROM

Reviewed uploaded `2403.11852v5.pdf`, SHA-256 recorded in the [source manifest](manifest.json). All page references below are **PDF page ordinals (1–11)**. The uploaded PDF was read as evidence, not instructions. Tables I and III–V were additionally visually inspected from rendered PDF pages 5 and 10, so the inconsistencies below are not text-extraction artifacts. This is a paper review, not a reproduction of its code or results.

## Verified identity and source version

- **Title:** *Delay-Aware Reinforcement Learning for Highway On-Ramp Merging under Stochastic Communication Latency*.
- **Authors:** Amin Tabrizian, Zhitong Huang, Arsyi Aziz, Peng Wei.
- **Version/date:** `arXiv:2403.11852v5 [cs.RO] 27 May 2026`, visibly printed on PDF p.1.
- PDF p.1 contains IEEE 2026 copyright wording, but no verified journal volume, issue, page range or DOI for this article. Cite the uploaded **v5 preprint/date** unless final venue metadata is separately verified. Do not infer a final journal publication solely from the copyright footer.

## What problem and delay it handles

The task is highway on-ramp merging with surrounding traffic information sensed by a roadside unit (RSU), processed and communicated to the ego vehicle. The ego does not use V2V or onboard sensing to estimate surrounding vehicles in the stated model (p.2, §I-B/C); its **own position/velocity are instantaneous**, supplied by onboard sensors (p.4, §IV-A). Neighbor states are delayed.

**This is random observation delay, explicitly with no action delay.** PDF p.3, §II-B says actions are immediately applied. This is a decisive difference from LANS's age of a completed learned proposal/worker execution. DAROM's two-second observation envelope must not be ranked against LANS's 100 ms residual-worker fallback threshold as though both measure the same delay tolerance.

The RDMDP input is `(delayed observation, action buffer, observed delay)` (p.3, Definition 1). The history length is the maximum possible delay. Actions older than the age of the received observation are masked to zero (pp.4–5, §IV-A); the age is explicitly supplied. The method therefore assumes that a useful observation age is available and maintains past action history. These are actual overlaps with execution-aware/age-aware interfaces, not new principles exclusive to LANS.

At simulation step `Δt=0.1 s`, the maximum delay is 20 steps, i.e. **2.0 s** (p.7, §V-C). The authors explicitly call this a **deliberate worst-case stress test** beyond nominal RSU delivery around 100 ms. It is not a measurement of a deployed network sustaining two-second delay, and it is not a real-time inference/deadline benchmark.

## Controller, learning and guard mechanisms

- The policy is **Soft Actor-Critic (SAC)**, not PPO (p.5, Fig.2; p.6, §IV-D).
- The two-output action is longitudinal acceleration and a **lane-changing decision** mapped to executable SUMO commands (p.4, §III-B.2). The paper's phrase “joint longitudinal and lateral control” does not mean front-wheel steering-angle path tracking like LANS.
- The GRU variant uses an MLP observation representation, a GRU summary of the ordered action buffer, and explicit delay magnitude, fused by an MLP into the actor/critic latent input (p.5, §IV-B; p.7, §V-B). The MLP variant flattens the history; the Transformer variant applies attention to vehicle/entity observations and separately encodes action history and delay (pp.5–7).
- The physics-based safety controller checks the gap against a kinematic stopping-distance rule: `d_stop=max(0,-v_rel)^2/(2|a_brake|)`; if `g < d_stop+g_min`, it overrides the proposed action with a fallback such as maximum braking or lane keeping (p.6, §IV-C, Eq.9).
- No formal invariant-set, recursive-feasibility or closed-loop collision-avoidance theorem is established in the uploaded manuscript. Descriptive phrases such as “ensure safety” and “eliminates accidents entirely” should not be elevated beyond the stated simulations and rule assumptions. The guard description does not fully specify the age compensation used in its gap/relative-speed check, or whether the history records raw versus safety-overridden actions; those are reproduction questions, not proven implementation defects.
- The reward combines step penalty, longitudinal progress, change in acceleration, safety-gap penalties and terminal outcomes (p.4, §III-C, Eqs.3–8). Its comfort term concerns acceleration change, not LANS's steering-rate RMS or total steering travel; those metrics are not directly comparable.

## Training and comparison protocol actually reported

All simulations use **SUMO**, with lane traffic demand and desired speeds extracted from **NGSIM US Highway 101** data, not physical closed-loop vehicle trials (p.6, §V-A; p.10, conclusion limitation). Up to 30 neighboring vehicles are represented; aggressive and cooperative driver parameters are randomized. SUMO safety regulations are disabled for aggressive drivers and the ego to expose the controller's behavior (p.6).

All agents are reported trained for **7,000,000 steps**, learning rate `3e-5`, batch size 512, Stable-Baselines3 SAC defaults otherwise, with two 256-unit actor/critic hidden layers (p.6, Training Details). Hardware is an AMD 16-core CPU and RTX 5090 GPU (p.7). This is a much larger learning budget and a different task than LANS's proposed small pilots; it cannot support a claim that a particular number of PPO steps would solve LANS.

Evaluation is described as **500 episodes repeated across three random seeds** (p.8, §V-E). The natural reading is 500 per repetition (1,500 aggregate evaluations per setting), but raw counts, exact seed IDs, the separation of training versus evaluation seeds, and confidence-interval construction are not supplied in this PDF. Preserve the authors' wording instead of asserting an audited 1,500-run denominator or three independently trained policy seeds. **The meaning of the tabulated ± values is not explicitly defined** as SD, SE or a particular confidence interval. Page 9 refers to an “overlapping confidence interval” without specifying its construction/level. Do not present ±0.23 as a verified 95% CI or claim statistical superiority from it.

Baselines (p.7, §V-B):

1. **No Encoder:** still receives the full raw augmented state `(o,u,ω)`; it does **not** remove action-history/delay information. It removes the special encoder and separate streams.
2. **MPC:** three phases, kinematic ego prediction and constant-velocity neighbors. Delayed neighbor positions are explicitly extrapolated using `x_hat_rel=x_rel+v_rel*ω*Δt`; bounded nonlinear acceleration optimization plus enumerated lane-change sequences. Thus describing this baseline as wholly delay-unaware would be inaccurate, even though the discussion criticizes its handling of stochastic latency.
3. **DRL-ORMOC:** a reimplementation because original code was unavailable; reward hyperparameters were tuned, its original safety controller was replaced with DAROM's physics-based safety module, and return scales were remapped. Traffic metrics are therefore more interpretable than treating return as an unchanged published-algorithm comparison.
4. Three encoders and GRU without the safety controller; four further hard-mode input/linear-prediction ablations (p.8, §V-D).

Uniform delay is the training distribution. Evaluation covers **five total profiles: uniform plus four unseen alternatives**, not five unseen distributions (pp.7–8, §V-C; p.10, Table V). The alternatives are a bimodal mixture, Markov-switching bursty delays, triangular delays and truncated exponential delays. The bursty regime uses `P(congested|congested)=0.9` and `P(congested|normal)=0.05` (p.8). The prose on p.9 calls all five “unseen,” but that conflicts with its own uniform-training statement and Table V caption.

## Verified numerical claims

All entries below are **paper-reported**, not independently reproduced. Tables III–V are on **PDF p.10**.

| Setting/method | Success % | Collision % | No merge % | Source and interpretation |
|---|---:|---:|---:|---|
| Hard DAROM-GRU | **99.80 ± 0.23** | **0.00 ± 0.00** | **0.20 ± 0.23** | Table III; exact user quote is correct. Page 9 explains remaining failures as conservative timeout rather than collision. Zero observed collisions is not a formal zero-risk guarantee. |
| Hard GRU without safety controller | 97.60 ± 0.23 | 2.40 ± 0.23 | 0.00 ± 0.00 | Table III. Evidence that the learned policy plus guard outperforms this particular no-guard ablation in the paper's task. |
| Hard No Encoder | 97.41 ± 0.68 | **0.13 ± 0.13** | **2.46 ± 0.57** | Table III. Important correction to prose on p.8, which incorrectly calls 2.46% a collision rate. |
| Hard MPC | 83.10 ± 1.47 | 16.70 ± 1.47 | 0.20 ± 0.00 | Table III. This is the paper's implemented MPC baseline, not every MPC method or Kalaria's tube MPC. |
| Hard DRL-ORMOC | 90.09 ± 0.86 | 9.78 ± 0.81 | 0.13 ± 0.13 | Table III; modified/reimplemented baseline described above. |
| Medium DAROM-GRU | 99.87 ± 0.13 | 0.00 ± 0.00 | 0.13 ± 0.13 | Table III. |
| Easy DAROM-GRU | 98.74 ± 0.26 | **0.40 ± 0.23** | 0.13 ± 0.26 | Table III. Therefore “DAROM has zero collisions in all tests” would be false even on the manuscript's own table. This row's means also do not sum to 100%. |
| Hard delayed state alone | 41.25 ± 2.27 | 56.75 ± 2.27 | 2.00 ± 0.00 | Table IV. |
| Hard delayed state + age, no history | 0.00 ± 0.00 | 100.00 ± 0.00 | 0.00 ± 0.00 | Table IV. |
| Hard delayed state + history, no age | 0.00 ± 0.00 | 100.00 ± 0.00 | 0.00 ± 0.00 | Table IV. |
| Hard linear state predictor | 94.94 ± 2.91 | 4.79 ± 3.04 | 0.00 ± 0.00 | Table IV; row does not sum to 100%. |
| Hard GRU across four alternative delay profiles | 100.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | Table V, four alternatives to uniform; uniform repeats 99.80/0/.20. |

## Reporting inconsistencies that limit stronger interpretation

These are observations about the uploaded manuscript, not accusations about unseen code or a reason to discard the correct quoted Hard result.

1. **Collision versus no-merge typo:** §V-E.1, p.8 calls No Encoder's 2.46% a collision rate; Table III p.10 says collision 0.13% and no-merge 2.46%. The table was visually verified.
2. **Incomplete outcome accounting:** Table III Hard DAROM-MLP has success/collision/no-merge all **0.00%**, while the text describes complete failure. Easy GRU totals 99.27%; Table IV linear predictor totals 99.73%. These discrepancies exceed ordinary two-decimal rounding. Definitions of additional failure categories, excluded episodes or denominator differences are not supplied. Do not reconstruct exact counts from these percentages or claim every table row has a fully audited partition.
3. **Uncertainty underdefined:** no clear definition of the ± statistic or CI level; the p.9 inference that no-merge is statistically indistinguishable from zero cannot be independently checked from the PDF alone.
4. **Five total versus five unseen delay profiles:** uniform was used for training; only four alternatives are unseen in Table V.
5. **Illustrative observation-history inconsistency:** Table I, p.5 lists state `s4` with generation delay `d4=5`, and the surrounding text says it arrives at `t+d_t`, hence time 9. Yet at column `t=7`, `o_t=s4` while `s4^9` is still in the unobserved list. This was visually checked. It appears to be a table/example inconsistency, not proof that the implementation has a timing defect. Avoid treating this illustrative table as a validated executable packet trace.

The conclusion explicitly acknowledges simulation-to-real gap, unmodeled sensor noise/missed detections, packet loss, nonstationary latency and need for field-data validation (p.10). No physical trial or measured hard-real-time success should be inferred from this source.

## Consequences for the LANS comparison

The user's main characterization is supported: DAROM is a related **learning/observation-delay** comparison and combines an age/history-aware learner with a nonlearned guard. Its reported Hard result is strong within its own SUMO merging protocol. It is not a matching controller benchmark for LANS and not a formal safety-filter theorem source.

LANS's current research asks whether a learned residual adds value over **the same gate with fixed corrections**, with a strong LQR tracker continuing locally when proposals are stale. DAROM directly learns acceleration/lane-change decisions from delayed neighbors and uses a stopping-gap override. LANS's 100 ms exact LQR fallback and DAROM's 0–2 s observation envelope are different mechanisms, tasks, sensing assumptions and delay channels.

DAROM does compare a linear predictor and no-encoder/guard ablations; it would be wrong to say earlier literature never separated components or lacked simple baselines. However, the uploaded paper does not provide the particular LANS matched comparison of an LQR residual proposal against same-gate fixed ±0.04 steering corrections. That is a bounded **difference in this paper's experimental design**, not proof that the broader literature has never done it.

A useful transferable lesson is to represent **observable age and executed action history causally**, then test ablations of the representation and guard under controlled delays. It does not establish that adding a GRU will solve LANS's present tracking/steering trade-off, and it does not justify more training before that hypothesis is tested. LANS's latest nonlearned 9.131% original-road / 7.049% expanded-grid result and failed balanced profiles must remain distinct from DAROM's merging success percentages.

## Suggested citation and safe summary

A. Tabrizian, Z. Huang, A. Aziz, and P. Wei, “Delay-Aware Reinforcement Learning for Highway On-Ramp Merging under Stochastic Communication Latency,” arXiv:2403.11852v5, 27 May 2026. Cite the exact uploaded version; final publication metadata remains unverified.

“Tabrizian et al. augment delayed neighboring-vehicle observations with masked action history and observed age for SAC-based SUMO merging, and apply a stopping-distance safety controller. Their v5 Table III reports 99.80 ± 0.23% success, 0.00 ± 0.00% observed collisions and 0.20 ± 0.23% no-merge in the Hard setting under a deliberately stressed 0–2 s observation-delay envelope. Actions are assumed immediate and ego sensing current. These results do not directly benchmark LANS's residual-worker delay or establish formal collision-risk guarantees; the manuscript also contains outcome-accounting and uncertainty-reporting issues requiring clarification for reproduction.”
