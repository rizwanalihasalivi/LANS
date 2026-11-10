# Actual-worker cohort declared before execution

After V1's2309 and V2's1240 CPU confirmation episodes and independent reconstruction finish,
run26 six-second actual-worker episodes sequentially. Both original-v8 and
selected new controller use each unchanged actor42/43/44 in four fixed conditions:
following/nominal, curved/ego-blackout, merge/PPO-crash and following/loss/PPO-stall.
Add selected-new actor42 following with planner-stall and planner-crash. Inject
crashes at1s; stalls last300ms. After1.5s no failed/stalled worker's stale proposal
may be selected. Source timestamps/TTLs and limits stay unchanged. Startup
warms returned-plan owner admission and is recorded separately.

Use actual spawned inference/solver processes and a fixed50ms release origin,
with no dropped tick or schedule reset. Measure sensor/wire input to issue,
and the complete cycle through plant propagation and inline JSON write/flush.
Retain all slow ticks in a separately hashed timing sidecar. Scope is finite
engineering observation on this shared cloud machine, not WCET/real-time proof.
Independent scalar physics/FIFO/source-age reconstruction is required. Fault
checks, safety, local timing and scheduled timing are separate outcome flags.
No new PPO training, altered policy weights, drafts, figures or tables.

The current actual-worker owner is analytical revision2, including the common
future-uncertainty/occupancy-tail supervisor. Historical original-v8 is retained
as a separately labelled comparison. Scientific gates may fail independently
of these engineering timing/fault checks; none is overridden.

Startup-only amendment after12 historical runs and one unmeasured new-owner
startup failure: requiring an accepted proposal can incorrectly reject a valid
fallback when the optimizer is infeasible. Warm a zero-error nominal empty road,
record real admitted/rejected counts, and explicitly compile the optional
planned-array cost overload. Require a ready, nonfailed solver process; actual
case solver rejection continues to use the unchanged owner admission/fallback.
The failed startup/log and all12 completed outcomes are retained; only the14
unmeasured cases resume, with no controller, actor, fixture or pass-gate change.
