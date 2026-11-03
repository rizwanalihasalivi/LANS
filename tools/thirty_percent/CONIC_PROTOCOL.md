# Projection-free joint conic diagnostic

The first 64 predeclared local shooting solves are complete and unchanged.
23/32 quality-constrained and 28/32 tracking-focused solves hit the 120-iteration
cap. Their rejected candidates/fallbacks are retained. They do not establish a
physical performance limit. Projection creates flat derivatives at saturated
commands, motivating a different numerical formulation rather than increasing
that original iteration budget.

On the same 32 already observed development cases, use exactly six sequential
linearization steps for each of two joint modes: quality-constrained and tracking-
focused. Start each mode from all matched LQR sequences. Linearize exact RK4 about
the current feasible trajectories, optimize actual steering variables with the
pinned Clarabel 0.9.0 conic solver (100 iterations, tolerances 1e-8), and project
proposals back into the original nonlinear residual/actuator constraints.

The convex subproblem minimizes the **sum of episode error-vector norms**, which
is the original mean episode RMSE up to a positive constant. It retains steering
angle/slew, per-cell progress, corridor and baseline-facing traffic-separation
halfspaces. A local linear residual-authority approximation is imposed where
consistent with the current actuator-saturated trajectory. Only exact projected
nonlinear metrics determine acceptance, so this approximation never grants extra
actual residual authority.

The quality mode uses joint second-order-cone epigraphs for heading and steering-
rate norms with the original <=110% across-case mean requirements. This avoids
the first diagnostic's stricter per-episode quality condition. The tracking mode
omits those two quality requirements and must be labeled inadmissible if the
original mean quality gate fails. All modes retain per-case safety and >=99%
progress and use the same fixed acceleration and NPC truth sequences.

Trust radius is 0.05*0.8**iteration rad. Evaluate exactly five globally shared
line-search fractions [1, .5, .25, .125, .0625]; keep the lowest **actual** mean
RMSE feasible complete 32-case plan. Never mix favorable cases from different
modes/fractions or remove a failed case. Non-solved subproblems keep the previous
feasible complete plan, with status logged. Per-mode total is six convex solves,
no restarts or outcome-dependent budget enlargement. Nonlinear acceptance leaves
the old physical/quality/progress thresholds unchanged; convex constraints have
small strict-inside numerical margins.

This remains a privileged offline model/future-informed diagnostic, not a causal
hybrid/PPO result, equal-compute comparison, certified global nonlinear optimum
or impossibility proof. It cannot open reserved/Webots gates or replace the v6
4.827% / 1.131% findings. No learning or paid service is used. No drafts, figures
or presentation tables are generated. Record source/input hashes, all solver
outcomes, exact accepted raw controls and Python-physics replay audits.
