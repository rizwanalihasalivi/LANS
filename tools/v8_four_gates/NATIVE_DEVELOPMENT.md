# Timing mechanism ablation, before outcomes

Keep the published V2 numerical owner/actor and actual native1ms dynamics,
0.59rad/s actuator setpoint slew,50ms fixed releases and complete-cycle logging.
Test the two exposed diagnostic fixtures straight16/actor43 and sine8/actor42.
Four declared variants: published arithmetic/default resources; equivalent fast
RK4/default resources; published arithmetic/bounded resources; equivalent fast
RK4/bounded resources. Exactly8 twelve-second development runs. Retain all
outcomes, misses and failures. These are exposed engineering data, not final.

All variants explicitly warm both optional-plan cost overloads and collect
startup garbage before the release clock. Garbage collection remains enabled
during measured execution. Numerical limits/checks/candidate sets stay identical.
The optimized kernel passed independent scalar/vector dynamics, full rollout and
closed-loop command-equivalence tests; any remaining floating-point differences
must remain below the declared numerical tolerances and get fresh validation.

The bounded-resource launcher uses four allowed distinct physical CPU cores:
owner, physics/display, solver and inference. Only this launched simulator/job
and its own workers receive affinity changes. LP_NUM_THREADS=1 limits software
renderer parallelism; physics remains the original one-thread1ms integration.
No cycle is dropped, rebased, shortened or selectively retried. No background
training/CPU campaign runs during these timing observations. Choose a runtime
configuration only from development data, freeze it before independent cases.
