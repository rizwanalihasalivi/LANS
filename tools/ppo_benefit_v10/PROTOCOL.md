# PPO contribution study, frozen before new outcomes

Scope is PPO only. Shared v8 controller, guards, traffic supervisor, three old
actors, physical bounds, 150 ms proposal expiry and scoring remain unchanged.
No thesis draft, figure or presentation table. Work lives in an isolated worktree.

Test whether causal teacher initialization and explicit queue/model observation
improve actual learned contribution. New actors have a separately versioned
30-feature contract: original 17 plus estimated stiffness/uncertainty, command
delay, last submitted residual, issued command, first/last queued command and
next-application predicted lateral/heading errors. No true stiffness, future
measurement, future NPC trajectory or evaluation fixture enters the actor/teacher.

Query after issuing the current command. A single logical 50 ms response is used
at the next decision; the current command and queue are therefore known at query.
Actor observations include its previous submitted action. At 100 ms actuation
delay the strict 150 ms issue guard still excludes the response; preserve this
limitation. Do not relax expiry to increase selection frequency.

Collect 64 training-only randomized cases (RNG 524113); every complete case is
retained, including failures. A causal teacher predicts the next application state
using received ego state, estimated dynamics and the known command FIFO. It scans
65 scalar corrections over the unchanged +/-0.08 rad range, with v8's unchanged
robust admission and no old planned tail. This is a computed training label, not
a future-truth oracle. Evaluate the direct teacher as a separate stronger
analytical reference; do not attribute its algorithmic effect to PPO.

For each seed 42/43/44, initialize a 30-input actor from the corresponding old
actor where shapes permit (original feature columns retained, new columns zero),
then 32 fixed epochs of behavior cloning on the same full training dataset.
Reset optimizer explicitly because input dimension and reward change. Keep the
BC-only endpoint. Run exactly 16,384 genuine on-policy PPO steps per actor, with
no seed/checkpoint selection. Keep all three PPO endpoints and checkpoints.
Reward is 1000 times the difference in actual tracking/heading/rate/acceleration
cost against a separate matched adaptive-MPC shadow (8,4,.04,.002), clipped to
[-5,5], plus selected-PPO predicted relative gain clipped to [0,1], minus 20 on
collision or corridor failure. Prediction gain excludes every PPO candidate when
forming the analytical comparator. Delayed credit remains explicit; selection
counts alone are not performance evidence.

Before evaluation freeze source, all policies and 72 fresh fixtures from namespace
991123: four scenarios x three speeds x three delays x two mirrors. Random road
phase/amplitude/offset/heading/traffic are independent of training; nominal network
isolates PPO and action delay. Each case receives LQR, adaptive-only, direct
teacher, old v8 hybrid (3 actors), BC-only hybrid (3), new PPO hybrid (3): 12
episodes/case, 864 episodes. Whole six-second failure-penalized RMSE, heading,
command rate, progress, collisions and selection counts are retained. Compare
actors after averaging within each fixture, bootstrap the 36 scenario/speed/delay
strata (5000 draws, seed 991124), and report per-actor outcomes. Comparisons with
BC-only distinguish PPO fine-tuning from teacher initialization. Do not tune on
these outcomes; old final/reserved fixtures are unused.

Primary success is positive whole-run incremental improvement versus adaptive-only
and old v8 hybrid, with positive lower confidence bounds, no hybrid failures,
>=99% every-cell LQR progress and <=110% mean heading/rate for every actor. Report
all failed goals. Also report the stronger requested 30% separately; no guarantee
is made. Logical service and teacher computation are not actual-runtime evidence.
