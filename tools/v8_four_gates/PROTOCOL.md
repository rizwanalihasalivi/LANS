# Four-gate repair development

Base33507590. User requests resolution of tracking gain, every-case progress,
deadline and actual heading/steering-rate regression. Preserve all earlier code,
failures and frozen evidence. No PPO training, reward or policy-weight changes;
that work belongs to the other agent. No thesis drafts, figures or tables.

Targets remain >=5% whole-run RMSE gain against the strong R16 matched LQR with
a positive lower95% clustered interval, >=99% progress on every evaluated case,
zero current collision/corridor failures, and no increase in mean heading/rate
RMS for each actor. Retain the original >=1% nominal-optimizer comparison too.
For actual timing retain every response and full-cycle50ms miss, fixed release
origin, original logging and native1ms dynamics. A finite observed pass is not
a universal operating-system/real-world guarantee. Source/physical limits and
freshness rules cannot be relaxed to meet a target.

Use existing training fixtures and now-exposed older failure traces for diagnosis.
Earlier final sets are exposed regression data for this iteration. Declare and
freeze new independent final cases only after the development choices are fixed.
Record every attempted arm/failure; no actor/checkpoint selection or retries of
completed outcomes to obtain a pass. Apply analytical safety repairs equally to
matched learned and analytical references. Record original-v8 separately.

Initial mechanisms to test: discrete-time, steering-increment LQ preview to
reduce transient tracking/heading/rate jointly; continuous longitudinal barrier
projection to avoid hard TTC-boundary acceleration jumps; bounded/prewarmed
owner computation and controlled native process/thread resources. Profile GC,
JIT compilation, model/gain updates and phase CPU/wall time before attributing
timing causes. A failed gate must remain failed until fresh evidence passes.

The first preview feasibility probe is development-only: straight, sine and
lane-change references at8/12/16m/s, plant stiffness0.8/1.2, initial lateral0.3m
and heading0.005rad, phase1 and amplitude0.9, six seconds. Prediction stiffness
is fixed nominal1; plant stiffness enters only propagation/scoring. Evaluate
all16 fixed (heading weight0.1/1/4/16, increment weight0.05/0.2/1/4) pairs with
lateral weight1, input weight1e-4 and two-second preview. No traffic/safety or
final-validation claim follows from this feasibility probe. Keep all trajectories.
