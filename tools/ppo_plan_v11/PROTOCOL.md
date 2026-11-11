# PPO sequence headroom study

Target: at least 10% full-run incremental RMSE reduction versus the strong v8
adaptive/MPC reference, while also reporting LQR, old PPO and all quality,
progress and safety outcomes. Do not reinterpret this as a relative increase
of a tiny previous percentage. No improvement or publication outcome is assumed.
Keep all old evidence immutable and do not change the other agent's controller.
No thesis drafts, figures or presentation tables.

First diagnose a richer action before training. A typed proposal contains eight
normalized residual knots covering the two-second horizon. It retains original
observation/submission/wall timestamps. One 50 ms logical service and the strict
150 ms age bound remain. At issue, build the residual plan on the latest state,
align its time origin, project through the original steering/residual/slew bounds,
and apply only its first command after the original FIFO delay. Never relabel
predicted states as newly received measurements. The v8 analytical path remains
the matched comparator and fallback. A separate owner compares a fresh plan's
robust cost with that existing decision; it may replace a command only after
the unchanged collision/corridor and predicted 110% heading/rate checks pass.
No change to longitudinal supervision is authorized by this PPO-only study.

A causal computed teacher searches eight residual knots using only received
state, estimated dynamics, known command FIFO and CV traffic. Exactly two
coordinate sweeps, amplitudes 0.02 and 0.005 rad, eight knots, both signs, starting
from zero, are declared. Each trial is projected and checked using all current
robust models. Rank by the same mixed cost; no true stiffness/future NPC truth
enters the search. This direct teacher is an analytical diagnostic, not a PPO
result or a certified global optimum/ceiling.

Evaluate all 64 existing training-only calibration fixtures once for each of
LQR, v8 adaptive/MPC and the causal sequence teacher: 192 six-second episodes.
Use the original whole-run failure penalty and gates, retain every failure and
fallback, and save full states/commands/proposal timestamps and source hashes.
The teacher's measured effect determines whether its training labels provide
useful demonstrated headroom; absence of 10% is not a mathematical impossibility
proof. Any subsequent model training or prospective evaluation needs its own
declared fixed budget and independent new cases. Earlier opened v10 cases remain
diagnostic records, never fresh final validation.
