# Matched closest-mechanism reference, before outcomes

Implement a delay-shifted command CBF-QP reference using the mechanism described
in Kalaria/Lin/Dolan, arXiv2208.13856v1 PlanB and Appendix. The inspected primary
review is docs/research/primary-papers/kalaria.md. Do NOT call this full original
paper reproduction or inherit its empirical results, tube/invariant proof,
INFLUENCE delay estimator or actuator-lag guarantee.

Explicit adaptations: the common LANS six-state dynamic bicycle and RK4 plant,
current command FIFO forecast, original-age neighbor CV packets and uncertainty,
scalar steering (shared bounded acceleration retained), road-error/circle
barriers, and the same angle/rate/0.08rad residual envelope as every comparator.
For each current model point derive hddot+2*omega*hdot+omega²*h>=0. Neighbor
uncertainty radius grows at the unchanged0.6m/s. Lane h=1.75²-error²; obstacle
h=distance²-radius². Solve the one-dimensional constrained minimal-command-
deviation QP by interval projection, with a fixed0.001 input-rate regularizer.
Use LQR as the nominal command to avoid any PPO optimization/actor selection.
If infeasible, retain the same explicitly labelled analytical recourse/fallback.
Pointwise CBF tests with approximate models do not establish sampled-data,
intersample or recursive safety. Independent trajectory scoring remains primary.

Evaluate exactly three frequencies1/2/4 on the64 existing training-only cases.
Select lowest failure count, then lowest whole-run mean RMSE, frequency tie-break.
Record all192 outcomes and whether the selected reference satisfies original
quality/progress limits. Never weaken or discard a failed reference. Freeze its
frequency before any fresh confirmation. The original v8 robust predictive
controller is also retained as a stronger matched control reference; existing
geometric adaptations are not misrepresented as the closest delay-aware method.

This closes a concrete mechanism-level comparison gap, not the full original
vehicle/steering-lag/racing-line experiment or a universal novelty claim.
No new PPO training, drafts, figures or presentation tables.
