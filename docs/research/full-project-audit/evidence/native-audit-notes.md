# Native/worker audit corrections

Owned source audit completed. All edits are uncommitted in the shared worktree; no historical results/models or shared Webots installation modified. Sources now stable for consolidated testing.

## Confirmed bugs fixed

1. **Worker startup failures/timeouts leak process/queues; native controller exceptions skip worker close.** `research/worker.py` now closes resources on failed initialization and makes close idempotent; invalid delays/nonfinite simulation timestamps reject before scheduling. Both `controllers/research_validation` and `controllers/gated_validation` wrap execution in `ExitStack`, registering worker close immediately after successful construction. The range-matched wrapper cleans up if its mapping log cannot open and closes its log in finally. Tests inject startup error/timeout; actual spawned worker smoke verifies one in flight, busy drop, minimum simulated delay, subsequent request and process shutdown.
2. **Simulator launcher timeout kills only shell, leaving Webots/Xvfb descendants alive.** New `research/native_process.py` starts a dedicated process group, signals whole group on exception/timeout, waits/reaps launcher, and kills remaining group members. Applied to run-physical, revision2 native runner and revision3 native_smoke. A real parent/grandchild test reproduces timeout and verifies descendant is gone or a non-running zombie awaiting host reaping; launcher is reaped. It does not claim the executor can reap non-child descendants itself.
3. **Concurrent old native runs using the same case name reuse the same generated world path.** `run-physical.py` now keys private generated projects by resolved output destination, consistent with later native runners. Two output directories with the same case name have distinct projects/worlds. Config/output paths resolve absolute.
4. **Old physical analyzer trusted RMSE/max from metrics.json rather than recomputing raw CSV.** `analyze-physical.py` recomputes executed RMSE/max and failure-penalized RMSE when present, validates summary consistency, checks scheduled counts and handles a one-row trace's empty wheel-rate differences. A copied real native fixture with corrupted summary RMSE is rejected; original fixture passes.
5. **Old physical analyzer counted held packets repeatedly for inference quantiles.** It now counts each observation packet once and reports unique packet count. A ten-times-held packet plus one fresh packet yields two inference durations, not eleven. Control-tick action age remains measured over control ticks as intended. This changes interpretation of old per-inference timing recomputation; original archived timing reports are immutable.

## Tests and evidence

- Seven tests pass: `integrations/webots/research/test-native-boundaries.py -v`; captured `/tmp/lans-native-boundaries.txt`.
- Real spawned policy worker smoke passes: `/tmp/lans-native-worker-functional.json`, reproducible script `/tmp/lans-native-worker-check.py`. No canonical worker-test.json overwritten.
- Two actual private Webots smoke cases completed: LQR and legacy gated residual,20m/s DLC, nominal noise seed880501,3s/300control ticks after10s warmup. Both survived. Output `/tmp/lans-native-audit-smoke`, log `/tmp/lans-native-smoke-log.txt`. RMSE0.051640932m and0.050709710m are only interface smoke numbers; no performance conclusion. This run exercised final controller/worker cleanup code before the launcher process-group helper was added; the later helper is tested with real parent/descendant timeout injection. No full native campaign or new student native transfer was run.
- Recomputed historical native metrics/source archives using corrected analyzer without its canonical-writing `main`: `/tmp/lans-native-metric-audit.json` (75 cases verified successfully).
- `git diff --check` passed.

## Changed files

- integrations/webots/research/worker.py
- integrations/webots/research/native_process.py (new)
- integrations/webots/research/test-native-boundaries.py (new)
- integrations/webots/research/run-physical.py
- integrations/webots/research/analyze-physical.py
- integrations/webots/research/revision2/native/run.py
- integrations/webots/research/revision3/native_smoke.py
- integrations/webots/controllers/research_validation/research_validation.py
- integrations/webots/controllers/gated_validation/gated_validation.py
- integrations/webots/controllers/range_matched_validation/range_matched_validation.py

## Scope and implications

Inspected adapter units/signs, open-loop controller, native physical/gated/range controllers, original and gated native runners/analyzers, worker lifecycle, and shell launch wrappers. Pure adapter units were already covered by existing tests; no new physical sign/units bug found. Native fixes address resource reliability, output isolation and evidence auditing. They do **not** explain the surrogate student/PPO plateau at2% or establish5–10% headroom. Existing native worker is still the explicit legacy9-feature policy interface; supervised20-feature student is not silently loaded or claimed validated there. Historical frozen-source runners should still reject mismatched source snapshots; source changes do not retroactively validate an old campaign as a current rerun.
