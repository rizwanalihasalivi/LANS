# Integrating the PPO-only experiment

This worktree changes no shared v8/v9 controller source. New policies have the
`v8-queue-model30-after-issue-delay50-v1` contract and cannot use the legacy
17-feature loader. `inference.load_policy` checks contract, shape and model hash;
`AsyncPolicy` supplies a bounded spawned worker with original timestamps.

At each owner tick, ingest current packets and poll/accept the previous reply,
then issue the controller decision. After issue, call
`core.observation(owner, now, last_response_residual / .08)`, and submit that
30-vector with the original received ego timestamp. Update the remembered action
when its reply becomes available, even if freshness admission rejects the reply.
Never mark a model-predicted state as a new sensor observation. Missing ego data
must retain analytical fallback. Close workers outside timed control ticks.

The model was trained with one 50 ms logical service and v8's original robust
guards/quality budget. A different supervisor, guard, observation timing, model
estimator or service distribution requires a new matched validation. The 100 ms
command-delay condition still reaches the 150 ms expiry boundary and excludes
learned authority. The adapter does not relax this bound. Actual-worker unit tests
check identity and deterministic inference, not hard real-time performance.

Models for all seeds, BC-only controls, source snapshots, protocols and raw
outcomes are retained by the evidence package. A saved endpoint is a research
candidate; final promotion depends on the reported matched outcomes. Other agent
work on safety/progress/timing can be combined later after independent review.
