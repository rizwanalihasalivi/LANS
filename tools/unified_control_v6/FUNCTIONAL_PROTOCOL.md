# Selected-controller actual-worker functional diagnostics

Exactly nine six-second checks: each original policy seed 42/43/44 on nominal
following, curved ego blackout, and merge worker crash. Use the selected shared
planner/horizon from training-only calibration, fixed speed 12 m/s, stiffness
0.8, zero command delay and the same functional fixtures as the recorded v5
instrumentation. Do not select a best actor, omit a slow case or retry deadlines.

Record complete input-to-issue and plant-cycle timings, misses above 50 ms,
collisions/corridor exceedances, source ages and raw physical/FIFO replay.
Record matrix/JIT startup separately; warm the complete declared speed/stiffness
grid before timing, without inspecting a test trajectory. Run after the CPU
simulation campaign, with no competing experiment workers.

The Python instrumentation in v5.live is reused with explicit process-local
Controller/Config/warmup bindings; batch protocol/snapshots record the actual v6
sources and bindings before execution. Instrumentation is unchanged on disk.
These are limited functional engineering diagnostics. The original full
multi-actor formal runtime promotion and final Webots prerequisites are not
bypassed. A functional pass cannot change a failed statistical promotion gate.
