# Native inner-loop and collection development, before outcomes

The8-run kernel/resource ablation did not meet the complete-cycle deadline.
Preserve all misses. On the same exposed straight16/actor43 and sine8/actor42
fixtures, run exactly3 variants for12seconds each: Python loop with startup
freeze; equivalent C loop with ordinary collection; C loop with startup freeze.
All use the equivalent fast owner,4 owned CPU roles and LP_NUM_THREADS=1.

The C function calls the same native Driver setters, Driver step and two sensor
reads at every original1ms substep. It neither batches nor skips any physics,
driver, sensor or actuator samples. Stub-library tests compare every commanded
setpoint and cruise call, final state, extrema and simulator-stop propagation.

Startup collection/freeze occurs after full physical/solver warmup and before
the release clock. The collector remains enabled. Imported/startup object graphs
enter the permanent generation; runtime allocations still collect normally.
Unfreeze and final collection occur during shutdown. GC events and peak RSS are
recorded; no pause is removed from measured response/full-cycle timestamps.
Fixed50ms releases, inline trace flush, original1ms dynamics and all gates remain.
No background CPU experiments are permitted during these observations.
