# Fixed actual-worker cohort

After training, calibration and logical evaluation CPU jobs finish, execute one
fixed 20-check cohort: v8 synchronous with original three policies and v9 selected
asynchronous with new three policies, each on nominal following, curved ego
blackout and merge with PPO-worker crash. Add two v9 seed42 nominal-following
checks with planner stall 300 ms and planner crash at 1 s. Every check lasts six
seconds, 50 ms control period. No failed or slow case is retried for selection.

Warm gain/JIT tables and spawned solvers before measured ticks, record startup,
and close the warm planner before creating the evaluated one. Close all workers
on completion and exceptions. Capture full input-to-issue and cycle times,
deadline counts, stale/failure flags, applied commands and native worker ages.
Warm the returned asynchronous plan through owner-process admission before
discarding the warm controller; fault injection applies only to measured workers.
Record actual release lateness and completion measured from the scheduled
release as well as local execution duration. Worker crash injection occurs before
the local timer and is included in scheduled-release timing. Local budget misses
and periodic deadline misses are distinct outcomes.
Planner failure removes its proposal; remaining separately validated controller
candidates can operate. PPO-worker failure retains the common analytical fallback.
State/trajectory safety remains tested, not formally guaranteed.

The paired roles differ in both architecture and actor weights. Their timing
comparison cannot isolate a pure architecture causal effect. Logical simulated
solver service is 50 ms; process service is measured, never invented or substituted.
Zero observed deadline misses would be finite cloud evidence, not WCET or a
target-hardware guarantee. Every miss and every failed trace is retained.
