# Strict-quality tracking objective, before development outcomes

The fixed-weight preview feasibility probes showed real trade-offs and are kept
as failed/partial development attempts. Test a different mechanism: preserve a
fixed nominal R16 backup/reference, identify the plant only from received ego
transitions, and use that estimate in the asynchronous conic planning proposal.
Actual owner admission independently reconstructs every candidate on three model
points, using the nominal R16 reference, original safety/residual/actuator limits,
and no predicted heading/rate energy increase (numerical tolerance1e-12).

Rank eligible commands by tracking SSE, the actual primary RMSE objective. The
old mixed objective's input-magnitude term is not a reported primary score; it
must not veto a tracking/heading/rate Pareto improvement. No measurement, physical
constraint, original gate, baseline gain or source freshness is changed.

Evaluate all four fixed arms: horizon2/3seconds and planner cap factor1/.995.
The slightly tighter planner cap reserves nonlinear-projection headroom; owner
heading/rate caps remain1. Matched R16 reference uses horizon2, the original
fixed configuration. Different candidate planning horizons are explicit algorithm
parameters, not a changed baseline. Shared continuous acceleration guard uses
the selected development frequency3 for all current roles.

Use the64 historical training-only fixtures, one matched LQR plus nominal and
adaptive versions of each arm: exactly576 six-second records. No PPO training or
policies are used here. Retain every raw trace. Eligibility: zero failures,
every-case>=99%matched-LQR progress, mean heading and rate no higher than LQR in
each role. Report5%tracking gain separately; select eligible arm with lowest
mean RMSE. If none passes, preserve the failure and continue development before
opening new final cases. All future validation choices/inputs freeze first.
