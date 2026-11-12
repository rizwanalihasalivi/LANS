# V13 development and completion protocol

The user now authorizes the shared collision repair, useful guarded PPO,
heading repair, new evaluation, actual runtime and final Webots validation.
Historical v8–v12 code and raw records remain unchanged. Work is isolated on
`research/ppo-complete-v13`. No thesis drafts, figures or presentation tables.

The previously opened v11/v12 cases are development/regression evidence, not
untouched confirmation. Initial diagnosis already establishes that case53
commands maximum braking from the first tick; braking itself creates its
crossing conflict. A first general causal brake-or-clear prototype has passed
that opened case. Broader repair tests and mathematical replay remain required.

All matched controllers receive the SAME shared safety filter. Original
steering/residual/slew, acceleration/brake, corridor, collision buffer,
uncertainty and 150 ms proposal-age bounds remain. Target speed remains a
tracking target, not an invented physical maximum. Any temporary clearance
acceleration and speed overshoot are recorded. Missing/stale data retains the
conservative fallback. No special-case fixture IDs, future traffic truth,
timestamp renewal, removed failures or weaker references.

The new neural contract is current-tick, 55 received/model/queue/anchor/history
features and eight bounded analytical-anchor corrections. Planning produces a
provisional reference, then bounded inference and final admission occur before
physical actuation. Actual runtime must establish completion within the 50 ms
owner deadline, with the original real source timestamp and wall age. The
logical Python model alone does not certify actual runtime. Old after-issue
weights are not silently reinterpreted under this changed contract.

Zero action exactly reproduces the repaired analytical reference. Fixed
backtracking may project corrections while retaining original robust cost,
quality and physical tests. A tail-only hypothetical cost improvement is not
credited as an applied PPO control. Two declared DEVELOPMENT choices may be
compared: original 110%-of-local-LQR quality guards, and an additional stricter
nonworsening quality bound relative to the exact winning analytical anchor.
The chosen configuration freezes before prospective evaluation. The extra
bound is not silently relaxed after a fresh outcome.

Learning repairs: the six-second horizon is a true terminal; its final
observation is physical/causal rather than zero padding. Remaining time and
running received-error/heading/applied-rate energies are observable features.
The exact primary reward component telescopes to negative penalized episode
RMSE with gamma=1, including all unrun failure ticks at the unchanged 6.25 m²
penalty. Constraint/feasibility reward components are separately declared and
logged; no clipped shadow-cost difference substitutes for the primary score.
Shadow ground truth may evaluate training reward/constraints only and never
enters actor features. Independent actor/critic Adam updates and gradient
clipping prevent actor KL stopping from starving the critic; actual optimizer
steps are logged, never conflated with SB3 epoch counters.

Before expensive three-seed learning, test opened-case zero-action identity,
all original guard boundaries, physical delayed action effect, finite-terminal
reward semantics and a causal computed development teacher's feasible headroom.
Sparse teacher headroom is not a global impossibility proof. Any next training
budget, initial imitation, continued-imitation control, random/fixed-proposal
projector control, endpoints and fresh cohort namespaces receive a separate
frozen prospective protocol before their outcomes are opened. This file does
not pretend to register already observed development outcomes as prospective.

The target remains >=10% full-run incremental mean RMSE gain against the strong
matched repaired adaptive/MPC controller, confidence of benefit against initial
and continued imitation and other strong controls, zero safety failures, every
case's progress >=99% of matched LQR, and every actor's mean heading/steering-rate
RMS <=110% of matched LQR. A >=10% lower confidence limit is reported separately.
All seeds/cases/delays/failures remain. Final validation uses additional untouched
cases after development freezes, followed by actual runtime and physically native
Webots transfer. Runtime/native readiness smokes are labeled as such and cannot
substitute for the final same-controller test.
