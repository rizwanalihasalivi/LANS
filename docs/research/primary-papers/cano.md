# Primary-paper review: Cano Córdoba et al. (ICAPS 2023)

Reviewed the complete uploaded PDF, with direct visual inspection of PDF pages 4–5 for Figures 3/5 and Tables 1/2. This is primary-source verification, not an execution or reproduction of the authors' software. Statements in the PDF were treated as source material rather than instructions.

## Identity and citation

Filip Cano Córdoba, Alexander Palmisano, Martin Fränzle, Roderick Bloem, and Bettina Könighofer. **Safety Shielding under Delayed Observation.** *Proceedings of the Thirty-Third International Conference on Automated Planning and Scheduling (ICAPS 2023)*, pp. **80–85**, 2023.

- Identity, authors, conference and copyright year: PDF p. 1 / printed p. 80.
- Six-page proceedings paper; the printed page sequence is 80–85. PDF p. `n` corresponds to printed p. `n + 79`.
- Uploaded filename: `03549-ICAPS.CanoCordobaF.pdf`.
- Uploaded-file SHA256: `49f610d86eb6ecb7dd644c12beab802eb0b45f6da695cb3dd06f10098a664c94`.
- The PDF does not provide a verified DOI or a formal revision number. Do not infer the conference date from PDF creation metadata (13 June 2023).
- The authors give a reproduction-code link in the footnote on PDF p. 2 / printed p. 81: `https://github.com/filipcano/safety-shields-delayed`. That repository was not inspected or executed in this review.

## Method, information and safety scope

**Finite safety game and permissible actions.** The environment is a two-player game: environmental inputs are chosen adversarially and the agent chooses actions. A safety specification marks unsafe states. A maximally permissive winning strategy contains the actions that preserve avoidance of unsafe states indefinitely in the game. A shield passes a proposed action if it belongs to that strategy, and otherwise replaces it with a permitted action. Source: “Preliminaries – Shielding without Delays,” PDF p. 2 / printed p. 81, Steps 1–3.

**The delay is delayed information, not a late residual worker.** “Shielding under Delayed Inputs,” PDF p. 2 / printed p. 81, assumes sequential delivery through a FIFO information channel and a worst-case delay `δ ∈ N` time steps. The shield sees a proper prefix of state history rather than the current state. It must decide the current action from stale information and latent-action history. On PDF p. 3 / printed p. 82, Step 3 requires memory of `δ` latent actions and computes winning strategies for increasing delays, pruning states that cannot be controlled at smaller delays. It is a synthesis for a declared worst-case delay bound, not an online computation-delay estimator. The reported CARLA plots use specified discrete delays; they are not a measured distribution of time-varying packet jitter, reordering or worker deadlines.

**Corrective-action choice.** PDF p. 3 / printed p. 82, Step 4 introduces two properties: controllability is the maximum delay for which a state remains controllable, capped at `δ_max`; robustness is the shortest path length to any unsafe state. Among safe corrective actions, the shield maximizes an average property over the forward set consistent with the stale state and latent actions. These properties target lower future intervention, rather than RMSE improvement over an LQR baseline. The paper reports the robustness heuristic as much cheaper than the controllability heuristic while achieving similar intervention behavior.

**Guarantee qualification.** The formal safety claim is for adherence to the winning strategy of the declared safety game under its delay/model assumptions. It is not unconditional physical-vehicle safety under arbitrary model error or arbitrary delay. The finite state/action/input abstraction, environmental movement bounds, declared delay bound and existence of a permitted action matter. In CARLA, the paper explicitly admits occasional empty strategies due to discretization errors. Its empirical absence of specification violations in those runs should be reported separately from the game-level guarantee. This is particularly important when comparing to LANS, whose performance gate has no equivalent formal winning-set construction.

**Computational scope.** PDF p. 3 / printed p. 82 describes worst-case delayed-game complexity as `O(|S|^δ)` and uses incremental synthesis to reduce the practical burden. Table 1 reports **shield synthesis time**, not online per-tick latency, inference time or a hard-real-time bound. The runtime/synthesis platform is AMD Ryzen 9 5900, 32 GB RAM, Ubuntu 20.04 (PDF p. 3 / printed p. 82, CARLA experiment introduction).

## CARLA experiments and exact claims

The CARLA agent is the default autonomous driver modified to be more reckless; the experiments do not train a learned residual policy. The continuous simulator is represented through a deliberately conservative discrete safety model, overestimating acceleration and underestimating braking. Both CARLA scenarios use the robustness-maximizing shield. Source: “Experiments – Shielded Driving in CARLA,” PDF p. 3 / printed p. 82.

### Cars at an uncontrolled intersection

- Each car is represented by distance to the crossing and velocity. Distance grid: `{0, 2, 4, …, 100}` m; speed grid: `{0, 1, 2, …, 20}` m/s. Source: PDF p. 3 / printed p. 82, “Shielding against Collisions with Cars.”
- Actions are accelerate, brake or coast. The abstraction uses time step **0.5 s** and acceleration/braking **±2 m/s²**. Source: PDF p. 4 / printed p. 83, shield-computation continuation.
- Figure 3 explicitly shows **0, 0.5, 1.0 and 1.5 s** delays. Higher delays trigger earlier and longer braking/intervention. The paper explains repeated on/off activation through conservative worst-case behavior that often does not materialize. Source: PDF p. 4 / printed p. 83, Figure 3 and car-results paragraph.
- The authors state that they tested “several safety-critical scenarios,” varied positions and velocities, and avoided collisions in all cases. **No numerical CARLA trial count, seed count, collision-rate denominator or confidence interval is provided.** Therefore a defensible summary is “collision avoidance was reported in all tested scenarios,” not an experimentally estimated 100% success rate with an invented denominator. Same paragraph, PDF p. 4 / printed p. 83.

### Pedestrians at a crosswalk

- The model permits pedestrians to move **1 m in any direction per 0.5 s** step. Its unsafe predicate is a fast ego vehicle (`v > 2 m/s`) close to the pedestrian (`|p_car − p_ped| < 5 m`) with the pedestrian closer to the crosswalk than the car. Source: PDF p. 4 / printed p. 83, “Shielding against Collisions with Pedestrians,” shield computation.
- Figure 5 plots activation distance versus vehicle speed for **0, 0.5 and 1.0 s** delays. Thus the user's broad “illustrated delays 0–1.5 s” is correct for the car example, but should not be presented as the legend of the pedestrian activation plot. Table 1 nevertheless includes three delay steps (1.5 s) in its pedestrian **synthesis-time** results. Source: PDF p. 4 / printed p. 83, Figure 5 and Table 1, visually inspected.
- The results explicitly state: “the game enters occasionally states with empty strategy due to discretization errors,” followed by the statement that the safety specification was never violated in their experiments. No numerical rate or number of empty-strategy events is given. Source: PDF p. 4 / printed p. 83, pedestrian-results paragraph.

### Table 1: synthesis times

These are seconds spent synthesizing shields; the delay columns are discrete steps of 0.5 s.

| Delay steps | 0 | 1 | 2 | 3 |
|---|---:|---:|---:|---:|
| Car example synthesis time, s | 1.5 | 13 | 48 | 167 |
| Pedestrian example synthesis time, s | 0.8 | 9 | 34 | 119 |

Source: Table 1, PDF p. 4 / printed p. 83, visually verified.

## Additional quantified evidence: gridworld

The paper is not limited to two CARLA demonstrations. Its gridworld compares robustness and controllability corrective-action heuristics. Each Table 2 point is an average of **100 plays of 2,000 time steps**, with stochastic robot/kid behavior and a four-dead-end layout. No standard deviations/confidence intervals accompany the table. Source: “Experiments – Shielding in a Gridworld,” PDF p. 5 / printed p. 84.

| Delay steps | 0 | 1 | 2 | 3 |
|---|---:|---:|---:|---:|
| Score, robustness | 42.5 | 34.3 | 31.5 | 26.8 |
| Score, controllability | 41.3 | 33.9 | 31.8 | 27.5 |
| Interventions, robustness | 90.9 | 107.5 | 114.1 | 122.0 |
| Interventions, controllability | 85.0 | 95.9 | 106.9 | 122.7 |

Source: Table 2, PDF p. 5 / printed p. 84, visually verified. These are mean counts/scores over the stated play horizon; the table does not label them percentages. Higher delay reduces score and increases intervention. The authors say the heuristics select the same corrective action in most states. Figure 7 compares synthesis times and expressly attributes much of the speed improvement over Chen et al. to a faster C++ implementation, with only minor algorithmic reasons (same page, “Results: Synthesis Times”). Do not turn this into a general learned-driving performance comparison.

## Assessment of the user's comparison with LANS

The supplied comparison is substantially accurate with the qualifications above:

| Dimension | This paper | Current LANS evidence |
|---|---|---|
| Safety mechanism | Synthesized winning strategy in a finite delayed safety game; override an unsafe action with an admissible one | Numerical predicted-benefit gate, age rejection and LQR fallback; no winning-set safety certificate |
| Information delay | Delayed environmental information reaches both agent and shield through FIFO; latent actions are tracked under a worst-case bound | The highlighted 100 ms case delays learned residual availability while the LQR path remains available; it is not the same delayed-observation problem |
| Decision objective | Permit all model-safe actions; select a safe replacement to favor controllability/robustness and lower future interference | Decide whether a fused correction is predicted to improve the chosen tracking objective over LQR |
| Task | CARLA collision-avoidance abstractions for intersection/crosswalk; separate gridworld intervention study | Declared lateral path-tracking/survival/steering metrics, with current R13 evidence from a surrogate |
| Empirical evidence | Qualitative CARLA collision-free claims with unspecified trial count; quantified gridworld averages | Explicit paired episode counts and raw tracking/steering records, but no comparable collision-safety or formal-shield guarantee |
| Learning attribution | Does not demonstrate a learned residual versus same-gate fixed corrections | R13 directly measures frozen student versus nonlearned fixed corrections; current best gain is nonlearned |

The delayed-input shield is strong evidence that delay-resilient runtime supervision already exists. It does not establish that every LANS execution detail or experimental attribution test has already been studied. Conversely, the different mechanisms do not prove that LANS has a unique or superior algorithm. The admissibility/robustness criteria in this paper already go beyond a trivial fresh/not-fresh check, so the novelty discussion should not caricature prior shields as checking only timestamps.

Recommended concise wording:

> Cano Córdoba et al. synthesize shields for finite safety games with FIFO-delayed observations and a declared worst-case delay, using latent-action memory and controllability/robustness heuristics to choose safe replacements. Their CARLA examples report collision avoidance in the tested scenarios, with car-example delays up to 1.5 s; the pedestrian case also discloses occasional empty strategies from discretization. LANS studies a different question—whether a freshness- and predicted-performance-gated residual adds tracking value over strong matched nonlearned corrections—and does not offer an equivalent formal safety guarantee.

Do not rank their 1.5 s observation delay against LANS's 100 ms residual-worker fallback, compare gridworld interventions to steering RMSE, or infer physical deployment safety from either simulator's collision/survival observations.
