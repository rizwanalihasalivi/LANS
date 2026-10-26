# Primary review: Kalaria, Lin and Dolan

Reviewed the supplied 12-page PDF in full, including methods, results, references and appendix. PDF page numbers equal printed page numbers. Tables I/II, Figures 7/8, and the p.7 displayed constraints were also visually inspected from rendered pages; no experiment or external bibliography lookup was performed.

## Identity and version

- Title: *Delay-aware Robust Control for Safe Autonomous Driving and Racing*.
- Authors: Dvij Kalaria, Qin Lin, John M. Dolan.
- Exact uploaded version: **arXiv:2208.13856v1 [cs.RO], 29 August 2022**, printed in the first-page margin.
- The running header reads **IEEE Transactions on Intelligent Vehicles**. This uploaded manuscript does **not** establish a final publication year, volume, issue, page range or DOI. Cite this exact arXiv version unless a publisher record is independently checked. Do not identify it as a verified TCST 2024 publication.
- This is distinguishable from the authors' earlier *Delay-aware robust control for safe autonomous driving*: the present paper explicitly calls [1] a preliminary version and lists its two extensions (p.2): dynamic rather than kinematic vehicle model; collision avoidance added to the learning-enabled-controller guard through CBFs. Reference [1] is listed as the 33rd IEEE Intelligent Vehicles Symposium, IEEE, 2022, with arXiv:2109.07101 (pp.10–11 reference list). Thus the earlier bibliographic uncertainty is partly resolved: the supplied paper itself identifies a preliminary 2022 IV work and a later, differently titled manuscript. It does not independently resolve all final-publication metadata.

## Method verified

1. **Task and actuation:** autonomous driving and racing with joint steering and pedal control. A dynamic bicycle model has lateral/heading errors and their derivatives, longitudinal speed/displacement and actual steering as states (p.3, Sec.III-D, Eq.3). Steering dynamics use a first-order lag, `delta_a_dot = K_delta (delta - delta_a)`. Pedal actuation delay is explicitly neglected for simplicity. The trajectory stack includes a minimum-curvature racing line and a Frenet planner (pp.2–3, Secs.III-B/C); future obstacles use constant longitudinal/lateral velocity prediction, while acknowledging that more sophisticated predictors could replace it.
2. **Different delays are handled separately:** a first-order steering actuator model; variable computation time `t_c`; and additional constant control-action-processing time `t_a`, with total `t_d=t_c+t_a` (pp.3–5, Secs.III-D/G). This is not just observation-age rejection.
3. **Plan A:** delay-aware robust tube MPC with shifted initial state, input/state constraints, disturbance tubes and a buffered command sequence. A low-level pre-compensator executes buffered controls in parallel at a higher frequency than the optimization cycle (pp.4–6, Secs.III-F/G/I, Eqs.10–11, Figs.2/5). The shift is predicted from known buffered nominal controls; disturbance margins account for uncertainty. IRIS constructs convex free-space constraints, with CBF treatment of boundaries/obstacles (p.5, Sec.III-G2).
4. **INFLUENCE estimator:** adaptive Kalman-filter variant jointly updates process-model parameters and process/measurement noise covariances to estimate a local computation-time upper bound (pp.5–6, Sec.III-H, Fig.4). Crucial qualification: despite broad abstract wording about no prior model/noise distribution knowledge, the detailed method explicitly assumes a **linear unknown process model** and **mutually uncorrelated, independent Gaussian process and observation noise** (p.6). It uses a mean-plus-uncertainty estimate and `beta=2` in experiments. Therefore describe it as adaptive estimation with unknown parameters/covariances, not distribution-free estimation or a deterministic deadline guarantee.
5. **Plan B:** a nominal black-box learning-enabled controller is rolled out from the delay-shifted initial state; a QP refines the resulting command sequence to track nominal commands, account for steering lag, minimize control effort and satisfy lane/collision CBF constraints (pp.6–7, Sec.III-J, Eq.16, Fig.6). It is a sequence-refining constrained guard, rather than a scalar residual blend onto an LQR default.
6. **Learner used in experiments:** a fully connected feed-forward network trained by **imitation learning from an MPC demonstrator**, with squared prediction loss and backpropagation (p.9, Sec.IV-B). Inputs include relative waypoint position/orientation, ego speed and target speed; outputs are steering and pedal. It is not PPO training. This also means LANS should not present teacher-to-student vehicle-control learning plus a model-based guard as a new combination by itself.

## Guarantees and assumptions

The paper invokes robust tube MPC/CBF safety reasoning and gives substantially more constraint reasoning than LANS's nominal tracking-benefit gate. That is an important methodological distinction, but it is still conditional reasoning:

- additive disturbances must lie in a bounded convex set `W`, with an appropriate invariant tube and state/input constraint tightening (p.4, Sec.III-F);
- the nonlinear vehicle model is locally linearized, and the additional linearization error is **assumed enclosed by a sufficiently large disturbance margin** (p.4);
- tube-set compatibility across cycles is required, with the detailed robustness proof referred to the preliminary work [1] (p.5, Sec.III-G3);
- computation-time bounding is probabilistic and relies on the stated estimator assumptions, rather than proving a finite worst-case execution time (p.6, Sec.III-H);
- steering-model identification, sensing/geometry and obstacle prediction must support the optimization's assumptions; this uploaded PDF does not supply a hardware end-to-end timing certification.

The full constrained formulation must not be equated with unconditional real-world collision safety. Conversely, LANS's tested exact fallback is not an equivalent invariant-set/constraint certificate.

Reproduction caution: Eq.15's printed derivative ordering and Eq.16's rendered CBF expression should be reconciled with the Appendix's explicit second-order condition on p.12 before porting equations literally. This is a manuscript-notation caution, not a conclusion that its empirical results or entire theory are invalid.

## Experiments and quoted numbers

The paper explicitly says **Gazebo for normal/non-racing driving** and **CARLA for racing** (p.7, Sec.IV introduction). All described tests are simulator tests; no physical vehicle deployment is reported in this uploaded version. It mentions racing speeds up to 180 km/h in the introduction (p.2), but this is not a universal validated operating envelope.

| Supplied claim | Primary-source verification | Necessary qualification |
|---|---|---|
| Plan A lap time 35.46 → 35.34 s, boundary violations 1 → 0 | **Correct**, p.8, Sec.IV-A2, Table I; CARLA Town06 closed-track portion, Fig.9 | Values are two run/condition rows, not a reported multi-seed mean with variance. No sample count, confidence interval or repeated-trial protocol is supplied for this table. Violation counts are counts for the reported runs, not collision probabilities. |
| Plan B learned-controller guard lap time 38.04 → 36.51 s, boundary violations 2 → 0 | **Correct**, p.9, Sec.IV-B1, Table II; Fig.12 | Again no repeated-trial denominator or uncertainty statistic is given. The change is delay compensation within the proposed guarded-controller setting, not evidence of learned policy versus an equally guarded nonlearned controller. |
| Delay-aware control prevents a collision when an opponent suddenly brakes | Reported qualitatively in p.8, Sec.IV-A3, Fig.10; opponent braking starts at t=2 s | `t=2 s` is the event time, **not a tested 2-second delay**. No trial success-rate denominator is supplied. |
| Overtaking at a turn remains within bounds with compensation | Reported in pp.8–10, Secs.IV-A4/IV-B2, Figs.11/15 | Qualitative scenario comparisons, not a matched LANS benchmark or broad statistical failure-rate estimate. |
| Computation delays are estimated and bounded | Figure 8 on p.8 depicts a roughly 10-second ROS trace with actual computation time visually around 35–60 ms and a higher estimate, approximately 55–72 ms after the initial transient | Approximate ranges are a visual reading of one plot, not a formally specified latency sweep, universal maximum delay tolerance, or quoted exact raw-data bounds. Prefer not to turn them into a headline number. Figure 7 on p.7 additionally labels a conservative fixed-compensation comparator as **0.2 s**; this is its assumed compensation interval, not proof that the actual delay was 0.2 s throughout. The legend calls the green curve “computation time taken,” while the caption explains it is the estimate including variance; orange is the actual time. |

For context only, the lap-time decreases derived from the two table pairs are about **0.338%** and **4.022%**. These are arithmetic derived from displayed times, not paper-reported tracking-error improvements. They cannot be compared numerically against LANS's 7–9% lateral RMSE reduction.

The uploaded version does not give a sufficiently complete common table of MPC horizon, sampling intervals, all weights, vehicle/tire/actuator parameters, computation hardware and repeated evaluation seeds to treat these tables as a ready-made reproducible matched benchmark. A reproduction would require obtaining/validating implementation details, and logging its actual computation costs under the chosen common conditions.

## LANS comparison and defensible positioning

Among these uploaded papers, this is a very direct **application-level comparison lead** because it combines vehicle dynamics, actuation/computation delay and constrained safeguarding of a learning-enabled controller. “Closest” is a scoped review judgment among the supplied set, not the result of an exhaustive literature search.

| Dimension | Supplied Kalaria version | Current LANS evidence |
|---|---|---|
| Main objective | Racing/driving trajectory control with lane/collision constraints and delay compensation | Lateral path-tracking assistance to a strong LQR, with heading/steering trade-offs measured |
| Control variables | Steering plus pedal; varying racing speed | Steering correction; declared speed families |
| Learned component | MPC-demonstrated imitation-learning FNN in Plan B | Current measured student is also supervised; further PPO benefit remains unproven |
| Guard | Tube MPC / QP command-sequence refinement and CBF constraints | Freshness/execution handling plus predicted tracking benefit and bounded residual fusion |
| Delay response | Predict delay, shift state, execute/refine buffered controls | Reject stale learned corrections and continue local LQR; tested 100 ms worker delay is not an equivalently delayed whole controller |
| Safety evidence | Conditional robust-constraint/CBF reasoning plus Gazebo/CARLA scenarios | Surrogate survival/bounds and exact fallback; no equivalent formal constraint certificate |
| Learned incremental benefit control | The supplied experiments do not report the specific LANS-style same-gate fixed ±0.04 residual ablation | R13 explicitly compares current student with both same-gate constants; constants improve tracking more, with extra steering activity |

The last row is a **specific absence in this supplied experiment set**, not a claim that no other paper has ever used nonlearned attribution controls. LANS has not reproduced Plan A/B under shared dynamics, constraints, delays or computational resources. No superiority claim follows.

Suggested report wording: “Kalaria et al. study active computation/actuation-delay compensation with constrained vehicle control and a learned-controller guard. LANS instead examines whether a selectively admitted residual supplies incremental tracking value over a strong local baseline, including same-supervisor fixed-correction controls. These mechanisms and evaluation tasks are different; the present experiments do not establish superiority over delay-aware robust MPC or equivalent safety guarantees.”

## Immediate corrections to the user's supplied summary

1. Both table pairs and boundary counts are accurate.
2. “CARLA experiments” accurately describes the quoted racing tables, but the paper's full experimental platform description is **Gazebo + CARLA**.
3. Call the trained controller **imitation-learned MPC student**, rather than implying PPO/RL training.
4. Retain conditional safety language; do not call INFLUENCE distribution-free or the local delay bound a hard execution-time guarantee.
5. Cite **arXiv:2208.13856v1, 29 August 2022** for this supplied PDF. The header supports a TIV manuscript identity, not the previously unresolved TCST 2024 citation.
6. The old LANS 1,080-episode/representative-trace comparison should be retained as historical and supplemented by the latest R13 confirmation/development results; do not reuse its trace-only steering percentages as current full-grid trade-offs.
