# Primary review: Wabersich and Zeilinger, uploaded arXiv v4

Source reviewed: `1812.05506v4.pdf`, 17 PDF pages. Page references below are PDF pages, which match the printed page numbers. Full layout text was read for the method, assumptions, theorem and experiments; Figure 4 on page 11 was also inspected in a rendered page image. This is a document review, not a reproduction of the algorithm or experimental results. No controller experiment was performed for this document review.

## Verified identity and version

- Title: **A predictive safety filter for learning-based control of constrained nonlinear dynamical systems**.
- Authors: **Kim P. Wabersich and Melanie N. Zeilinger**, ETH Zurich (p. 1).
- Version banner: **arXiv:1812.05506v4 [cs.SY], 17 May 2021** (p. 1).
- Page-1 footer says **“Preprint submitted to Automatica”**, dated **18 May 2021**. These two dates are distinct statements in the uploaded artifact, not a contradiction that needs silently fixing.
- The uploaded version does **not** itself establish the final Automatica volume/article number or DOI. The previously supplied `10.1016/j.automatica.2021.109597` is not printed in this PDF; keep final publication metadata unverified unless a separate primary publisher record is obtained. A reliable citation to the actually inspected version is the arXiv v4 identifier and date.

## What the method does

The filter is placed between an arbitrary proposed learning input and a constrained physical system (Fig. 1, p. 2; Sec. 3, pp. 3–4). It is designed to preserve constraints, while changing the proposed input as little as necessary. It is **not** designed to establish that the learner beats a strong nominal controller on tracking cost.

The formal plant in Eq. (1) is a deterministic discrete-time nonlinear system conditional on an unknown true parameter vector, with an available probability distribution over model parameters and a known initial-state distribution. State and input constraints are polyhedral (Sec. 3, pp. 3–4). The desired safety statement is the **joint event of constraint satisfaction over every time in the horizon**, Eq. (4), at probability at least `pS`; it is not merely a per-step expected cost or a per-step chance bound.

The nominal filter minimizes the norm of the difference between proposed input and the first planned input, subject to dynamics, state/input limits, a region where the model is known, and reaching a terminal safe set (Eq. (5), p. 5). Its uncertain-model version uses the mean model, tightened state/input/terminal constraints, and a state/input-dependent confidence-set constraint on model error (Eq. (6), p. 5; Sec. 4.2, pp. 6–8). The admissible confidence map avoids needing a uniform worst-case model-error bound everywhere and restricts backup planning to sufficiently confident parts of the state/input space.

A feasible backup plan leads to a known terminal safe set. If a new full-length plan cannot be found, the algorithm replans with a shrinking horizon; eventually the terminal safety controller/filter can be used (Algorithms 1–2 and Fig. 2, p. 5; explanation p. 6). Under uncertainty, the existence of a nearby tracking policy supports the feasibility proof; that particular tracking policy is not itself needed in implementation (p. 7). This mechanism is materially different from rejecting a stale residual and reverting to an unproven-safe LQR tracker.

## Exact safety assumptions and scope

The main statement is **Theorem 4.6**, beginning p. 8 and continuing p. 9, with proof in Appendix A.2, p. 16. It requires:

1. **Assumption 4.2** (p. 6): a terminal safe set inside the constraints, a suitable Lipschitz description, and a terminal safety filter that preserves state/input constraints for all future times once in that set.
2. **Assumption 4.3** (p. 7): local incremental stabilizability/tracking around the nominal predictions, represented by a bounded energy-like function and contraction rate, with bounded control corrections.
3. **Assumption 4.5** (p. 8): a valid set-valued model-confidence map, Lipschitz under the Hausdorff metric. Definition 4.4 explicitly requires confidence to cover the model-error event jointly across relevant states, inputs and times, rather than at just one time or query.
4. A sufficiently small confidence-map Lipschitz constant relative to the tightening factor, a sufficiently small admissible error-set scale `gamma`, and **initial feasibility** of optimization problem (6).

The result is **safety in probability at the selected level**, under these conditions. The nominal perfectly known-model construction is a different special case. Neither statement should be flattened into an unconditional safety guarantee under arbitrary model error, delayed/stale state estimates, computation overruns or failed solvers.

Section 4.3 (p. 9) acknowledges that proving exact design bounds may be difficult and supplies tuning guidance. Appendix A.3 (pp. 16–17) gives finite-horizon statistical offline verification based on sampled model parameters/initial conditions and a Hoeffding bound. That is separate from the reported learning trajectories and from LANS's empirical survival count. The theorem is stronger than LANS's present evidence, but its assumptions remain essential.

## Experiments and the user's numerical claim

### Pendulum (Sec. 5.1, pp. 10–11; Fig. 3, p. 10)

- Simulation swing-up with angle limits `−90° <= alpha <= 190°` and bounded torque; model parameters are initially uncertain.
- A bang-bang policy with two switching times is tuned using **Bayesian optimization**, not PPO (p. 10).
- **120 learning episodes** are shown. The model starts from **10 data points** near the stable downward position; a refined model uses **18,000 accumulated samples** and permits less conservative learning (Fig. 3 and results p. 11).
- Desired constraint-satisfaction probability **`pS = 0.95`**, horizon **`N = 50`**, sampling interval **`h = 0.02 s`** (pp. 10–11). Ipopt/CasADi is reported as solving the problem in real time (p. 11), but this does not provide a quantified worst-case deadline guarantee.

### Quadrotor (Sec. 5.2, pp. 11–12; Fig. 4, p. 11)

- **Simulation**, using the AscTec Hummingbird drone in **Bullet Physics SDK** with a rotor-force model; this is not a physical quadrotor experiment.
- Introductory description calls the physical model 12 states/4 inputs (p. 2). The filter's identified inner-controlled model uses **10 states and 3 inputs**, around hover, with an inner PD loop (p. 11). These descriptions refer to different levels of the model and should not be conflated.
- The task is approaching a near-ground point `(x,y,z)=(3,2,0.2) m` from hovering at `(0,0,3.5) m`; state constraints include `z >= 0.175 m` and `|vertical velocity| <= 1 m/s`; inner-loop inputs are normalized to `|u_i| <= 1` (p. 11).
- The learned outer controller is a saturated **PD controller whose gains are selected through Bayesian optimization**, not a neural PPO residual.
- Predictive-filter horizon **`N = 20`**; terminal safe region uses **`z >= 1.5 m`** with specified conservative PD gains; desired chance-safety level **`pS = 0.9`** (pp. 11–12).
- Model data are collected through **100 random step inputs applied for 60 seconds** at a safe altitude (p. 11). Preserve the paper's wording; do not invent a larger independent-trial count from it.
- Unsafe policy search yields ground contacts and vertical-velocity violations; Fig. 4 marks body-to-ground minimum distances below **0.01 m** as contacts. This is a body clearance criterion, not the same as the height state `z < 0.01 m`.
- **The user's core claim is verified:** p. 12 states that the filter **“enables constraint satisfaction during all 240 learning-episodes.”** The unsafe-policy comparison discusses 240 learning episodes on p. 11, and Fig. 4 displays unsafe/safety-augmented trajectories.
- The final reported safe learned trajectory has the filter **permanently inactive**, as encouraged by its objective (p. 12).
- These are **learning episodes**, not 240 independent held-out seeds. The cited result is descriptive experimental evidence in addition to the conditional theorem. No independent multi-seed confidence intervals, LQR-relative tracking-RMSE ranking, racing lap-time result, delayed-worker benchmark, or physical-vehicle experiment is supplied by this example.

## Important overlap that should be added to the LANS positioning

The overlap goes beyond putting a model-based gate around learning:

- The learner is trained while interacting with the filtered/safe system (Sec. 3, p. 4).
- The **pendulum reward/cost penalizes the squared difference between proposed and filtered input** (p. 10).
- The **quadrotor objective includes a heavily weighted intervention penalty**, `100 * norm(proposed input − filtered input)`, in addition to position error (p. 11).
- The final trained controller can operate without intervention (p. 12).

Therefore “include the supervisor during training,” “make the learner aware of intervention,” or “reduce supervisor intervention as learning improves” are not sufficient novelty claims for LANS. A legitimate narrower comparison concerns **incremental realized usefulness over a strong classical baseline and same-gate fixed residual controls under explicit delayed execution**, with tracking/heading/steering trade-offs measured. Even that is a research focus, not a proven first-of-its-kind claim.

The inspected paper's formal state-feedback problem and examples do not supply an explicit packet-age, asynchronous worker, stale-proposal or deadline-miss experiment. This bounds the comparison to this text; it should not be restated as proof that the authors' broader framework cannot be extended to delays.

## Suggested comparison wording

> Wabersich and Zeilinger formulate an MPC-based predictive safety filter that minimally modifies learned inputs while maintaining state/input constraints in probability under model-confidence, stabilizability, terminal-safety and initial-feasibility assumptions. Their simulated quadrotor study reports constraint satisfaction over all 240 learning episodes at a selected chance-safety level of 0.9. LANS currently offers empirical path-tracking and execution-fallback evidence, rather than an equivalent certificate; its specific question is whether learned residual proposals add measurable benefit over matched nonlearned proposals under the same performance gate.

Do not numerically rank the paper's 240 learning episodes against LANS's 7,776 episodes, or interpret LANS's count as a stronger guarantee. The task, constraints, learning procedure, evidence unit and safety claims differ.
