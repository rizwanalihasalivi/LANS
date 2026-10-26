# Primary-source review: Tearle et al., predictive safety filter for racing

Reviewed upload: `2102.11907v1.pdf`, eight PDF pages. The [source manifest](manifest.json) records the exact file hash. Citations below use **PDF page numbers**, because the uploaded version does not provide a reliable printed page numbering sequence. Full layout text and all eight page extracts were read; Figure 6 was also rendered and visually inspected.

## Identity and version

- Title: *A predictive safety filter for learning-based racing control*.
- Authors: **Ben Tearle, Kim P. Wabersich, Andrea Carron, Melanie N. Zeilinger**.
- First-page arXiv stamp: **arXiv:2102.11907v1 [eess.SY], 23 February 2021** (PDF p.1).
- This establishes the uploaded preprint's identity and date. A final venue, page range or DOI is not independently verified by this upload alone; do not add guessed final-publication metadata.

## What the method actually does

The filter accepts a proposed **full control vector** consisting of steering and drivetrain commands, rather than a bounded residual on top of LQR. It checks whether a constrained predicted trajectory can begin with the desired command and reach a known safe terminal set. When necessary it supplies an alternative first command, chosen to stay close to the desired one (PDF pp.2–3, Section II, Definitions 1–2; Section III, equations (3)–(4)).

The prediction problem includes state/input constraints at each stage and terminal membership in an invariant set. Its feasible backup trajectory provides a continuation towards states for which a local terminal controller is available. The enlarged online safe operating region is implicit in the backup-trajectory feasibility problem; it should not be described as an online retraining of the terminal controller (PDF p.3, Section III).

The prediction plant is a nonlinear dynamic bicycle model with **simplified Pacejka tire forces**. States include global position, heading, longitudinal/lateral velocity and yaw rate; inputs are steering angle and drivetrain command. Forward Euler supplies the discrete-time model. The main track constraints use the front two corners of a vehicle bounding box, not merely a point mass lateral error (PDF p.4, Section IV-A/B, equations (6)–(10)). The paper does not establish a general traffic-collision safety controller from these track constraints.

The terminal construction transforms the dynamics into track-relative coordinates, computes equilibria parameterized by road curvature, and uses a common linear feedback matrix with a quadratic Lyapunov function. A semidefinite program maximizes an ellipsoidal terminal set over gridded curvatures, followed by nonlinear verification over state and curvature (PDF pp.5–6, Section V, equations (11)–(19)).

### Smoothness is already present in this paper

Equation (5) adds a squared input-rate penalty to the deviation-from-desired-input objective. The text explicitly identifies rapid fluctuations between desired and filtered commands as a practical issue and states that the desired-command weight **W is much larger than the rate weight R_S**, so following the desired signal remains the primary objective (PDF p.3, Section III, equation (5)). Thus smoothing a supervisory controller using input-rate regularization is not, by itself, a new LANS contribution. This is also a directly relevant design reference for the observed LANS tracking/smoothness trade-off, although its objective and safety constraints differ from LANS's LQR-relative benefit gate.

## Safety claims and their boundaries

The mathematical framework defines safety as state and input constraint satisfaction at all times. Recursive feasibility and continued constraint satisfaction rely on **Assumption 1: a positively invariant terminal set and an admissible terminal control law**, together with feasibility of the initial optimization and the stated model dynamics (PDF pp.2–3). This is a formal control argument that LANS's nominal predicted-performance acceptance test does not possess.

However, the upload itself contains important practical qualifications:

1. **Constant curvature restriction.** The terminal invariance argument is valid on individual constant-curvature segments. The authors explicitly state that the guarantees “do not strictly hold” at instantaneous curvature changes between segments because the equilibrium changes. They rely on observed conservatism and treat segmentwise invariance as practically adequate; no additional treatment of the jump is implemented (PDF p.6, Section V-B, paragraph beginning “Note that the invariance guarantees…” and continuation at top of right column).
2. **Soft implemented constraints.** Track-width and terminal-set constraints are implemented as **soft constraints** to ensure optimization feasibility (PDF p.6, Section VI-A). Thus the implementation should not be presented as an unconditional hard-constraint certificate for every physical state and disturbance.
3. **Numerical verification.** The nonlinear invariance search of equation (19) was solved from **1,000 randomly selected initial conditions**, with objective never exceeding one (PDF p.6, Section VI-A). This is the stated numerical evidence; the upload does not establish that those local searches globally certify every continuous state/curvature combination.
4. **Model/state and optimization conditions.** The formal system is deterministic and uses the defined dynamics; the physical platform instead employs estimated state and real hardware. The paper does not supply an all-disturbance physical guarantee or a measured deadline-miss distribution (PDF pp.2–3 and p.6).

These qualifications do not erase the paper's formal framework or physical demonstration. They limit how strongly that theory can be transferred to its implemented racing experiment—and prevent a misleading comparison in which the paper is treated as either universally certified or merely another empirical gate.

## Experiments and verified numerical claims

| Claim | What the uploaded source supports | Location |
|---|---|---|
| Physical miniature vehicle | Kyosho Mini-Z **1:28-scale** RC vehicle on a **0.80 m** constant-width track | PDF p.6, VI-B |
| State estimation and actuation | VICON position/orientation, EKF full-state estimation, radio-commanded vehicle | PDF p.6, VI-B |
| Implementation rate | **80 Hz sampling frequency**, acados real-time-iteration SQP, **N=60** prediction steps | PDF p.6, VI-A |
| Computing platform | ROS on Lenovo ThinkPad P1, Ubuntu 18.04, Intel Core i7-9750H, 32 GB RAM | PDF p.6, VI-B |
| Terminal-set design | MOSEK, **21** equilibrium points over curvature **[−2.5, 2.5]**; **1,000** randomized verification initializations | PDF p.6, VI-A |
| Manual driver assistance | Figure 5 reports a **single lap**, including intentional missed corners/swerves, with intervention in steering and throttle; depicted trajectory stays in the track | PDF pp.6–7, VI-C; Figure 5 on p.7 |
| Learned controller | **DAgger imitation learning**, a feedforward network with **3 hidden layers, 64 units per layer**, ReLU; outputs steering and drivetrain commands | PDF p.7, VI-D |
| Learning inputs | Track-relative state plus **30 curvature values over the next 1.5 m** | PDF p.7, VI-D |
| Expert | Model Predictive Contouring Controller (MPCC), with offline labeling potentially using a longer horizon than real-time execution permits | PDF p.7, VI-D |
| Later learning performance | Trajectory aligns more closely with MPCC and shows substantially fewer major filter interventions | PDF p.7, VI-D; Figure 6 on p.8 |

An 80 Hz configured sampling rate corresponds to a nominal 12.5 ms period, but **the paper does not report a hard worst-case latency or missed-deadline guarantee**. Do not compare “80 Hz” directly against LANS's 100 Hz target as if either number certifies real-time deadlines. The N=60 and 80 Hz values imply a nominal 0.75 s horizon by arithmetic, but that derived quantity should be labeled as such if used.

The upload presents two application demonstrations, not a matched repeated-trial statistical performance campaign against LQR or fixed residual proposals. It contains no tabulated multi-seed survival denominator, confidence intervals, average lap-time improvement, or quantitative percentage reduction in intervention corresponding to the claims being reviewed. Figure 5 is one lap; Figure 6 shows multiple laps from selected learning iterations. “Track protection demonstrated in the illustrated physical experiments” is supported; a numeric zero-failure probability is not.

## Important correction: fourth versus fifth learning episode

The user's statement that the **fifth** episode has much less intervention matches the paragraph on **PDF p.7, Section VI-D**, which explicitly says “5th episode.” However:

- The lower Figure 6 legend on **PDF p.8** says **“NN Trajectory – 4th Iteration.”**
- The Figure 6 caption says **“first (top) and fourth (bottom) episodes of DAgger.”**

This discrepancy is visible in the rendered PDF, not an extraction artifact. The uploaded v1 is internally inconsistent. Recommended wording:

> “The illustrated later DAgger iteration has substantially reduced safety-filter intervention; the v1 text calls it the fifth episode while Figure 6 labels it the fourth.”

For a concise overview, omit the exact episode index and retain the qualification in a footnote/source ledger. Do not silently choose one number or describe a verified fifth-episode quantitative result.

## Relationship to current LANS evidence

**Close overlap:** learned or human proposed inputs pass through a predictive supervisor; a backup control mechanism supports safe continuation; the filter is designed to minimize unnecessary intervention; smoother commands are an explicit secondary objective; learned proposals are evaluated inside the closed loop. These concepts predate LANS.

**Different research question:** this paper filters the full steering/drivetrain command to satisfy track-related constraints while staying close to the proposed input. LANS currently blends a bounded steering correction with a strong LQR controller according to packet freshness and **predicted fused-command tracking benefit**, then compares learned proposals against identical-gate fixed ±0.04 rad proposals. Those matched attribution experiments are a defensible focus, but this five-paper review cannot prove that nobody has previously used such comparisons.

**Different evidence:** Tearle provides a physical small-vehicle demonstration and an invariant-set/recursive-feasibility framework, with the implementation qualifications above. LANS revision13 is a surrogate confirmation/development campaign: nonlearned original-positive gain replicates at 9.131%, full mirrored-grid gain is 7.049%, the student reaches 4.126%, and none of three balanced profiles qualifies for subsequent reserved/native/learning stages. LANS's survival thresholds and exact delayed-action fallback are not equivalent to this paper's track-boundary constraints or a physical safety guarantee. LANS's real-worker timing audit also reports missed deadlines; its current learner's simulated pending-context features remain a causal native-interface issue.

**Delay distinction:** this uploaded Tearle version does not present a dedicated communication/computation-delay estimator or a delayed-observation/action-age experiment comparable to LANS's packet-lifecycle study. This is a scoped observation about this upload, not a universal statement about all predictive safety filters or later versions of the authors' work.

## Recommended opening-report sentence

> “Tearle et al. demonstrate an MPC-based predictive safety filter on a 1:28-scale racing vehicle using invariant terminal sets and backup trajectories. Their nominal 80 Hz implementation and physical track-boundary demonstrations provide evidence beyond LANS's current surrogate performance gate, although their experimental implementation softens constraints and explicitly qualifies invariance across curvature changes. LANS instead investigates the incremental tracking usefulness of fresh learned residuals against matched nonlearned proposals; it does not claim equivalent formal safety, superior physical performance, or guaranteed deadlines.”

This review changes documentation only; it launches no controller experiment.
