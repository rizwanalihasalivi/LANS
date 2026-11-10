# Frozen v8 reliability confirmation — before fresh outcomes

Select only from completed 704 training-only calibration records under its
predeclared selector. Freeze that selection, all three original PPO endpoints
42/43/44, the selected CBF frequency, exact source and all cases before execution.
Do not train/reweight/select PPO endpoints or reuse v9 final cases for tuning.

Run 32 fresh balanced development cases (namespace31011000), 64 independent
final cases (namespace32011000), and the 32 original unopened v8 reserved cases.
The user's explicit request to complete v8 final validation authorizes this new
validation-only procedure despite the unmet30% goal. It does not retroactively
satisfy v8's old conditional promotion rule. Open this original reserved set once
after all choices freeze; no tuning follows those outcomes.

Each case has 16 records: common-recourse LQR/fixed/deterministic/nominal-MPC/
adaptive-only; selected asynchronous hybrid with all3 original actors; original
v8 synchronous hybrid with the same3 actors; cached v8 hybrid with common
recourse and the same3 actors; original v8 adaptive-only; calibrated scalar CBF
reference. The original v8 is a separately labelled frozen reference. Current
analytical/learned references share new recourse, bounds and source semantics.
The CBF reference is explicitly a Kalaria PlanB mechanism adaptation to the
LANS plant/constraints, not the paper's full lag-aware sequence/pedal controller.

Add all24 scenario/network stress cells under new communication namespaces and
the5 exposed training crossing failures as regressions. On those29 fixtures use
common LQR, optimized, adaptive-only and all3 current/original hybrid actors:
9 records per fixture. Total2309 six-second episodes. Keep every outcome.

Whole-run failure-penalized mean episode RMSE, actual heading/rate, collisions,
corridor, source age, actual limits, every-case progress and unc ertified-recourse
counts are retained (the mode name is uncertified_emergency_improvement).
Do not pool actor/frame counts as independent traffic seeds. Bootstrap5000 draws,
seed41011000; clusters are scenario/speed-stratum/communication stratum, with
actors and replicate cases averaged inside clusters. Record5%LQR/1%nominal
positive-confidence gates, <=110%quality and >=99%progress exactly. Also report
the30% flags separately; PPO-specific improvement remains the other agent's work.

Independently reconstruct raw dynamics, packet sourcing, FIFO, metrics and case
coverage. Only current Python safety pass permits native transfer. Negative or
small gains remain valid outcomes; no final case/actor is discarded or reused
to tune. No new drafts, figures or presentation tables.
