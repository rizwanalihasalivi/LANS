# V13 prospective learning and qualification protocol

Registered after the opened-case safety repair and headroom pilots; before any
v13 policy training, validation or final-case outcomes. No ten-percent result
is assumed. Opened v11/v12 cases are development/training data. The three
small headroom pilots and all failures/trade-offs are retained separately.

The shared controller is safety.Controller with plans.PlanMixin. Every matched
method uses the same causal brake-or-clear filter and original physical,
freshness, collision/corridor, robust cost and local110% LQR quality guards.
Final actor projection uses correction_amplitude=.08 and no extra anchor-only
quality restriction; this retains the original guards. The computed labeling
teacher uses an additional anchor-nonworsening quality constraint and mixed
model cost. This is explicitly a teacher restriction, not a hidden difference
between evaluated methods. Zero action is exactly the repaired analytic owner.

Collect full teacher trajectories on all72 already-opened v12 fixtures. Preserve
the paired zero-action trajectories, true physical/shadow traces,55 causal
queries, bounded8-coefficient labels, optimizer failures and model diagnostics.
Initial BC uses all real teacher frames (up to8640), weight10 for nonzero labels and1 for
neutral labels. Train seeds42/43/44 independently, MLP128x128 pi/value nets,
32 supervised actor epochs, batches128, temporary Adam3e-4, actor gradient
norm1.0. Initial log standard deviation is-2.5. The supervised optimizer is
separate from both true PPO optimizers.

Critic warmup is separately labeled:32 complete episodes per seed (at most3840
environment steps) under the deterministic initial BC actor, case RNG
seed90000+seed, with failures retained. Fit only the value network to gamma1 finite-task returns with
four passes/batches128 at critic rate1e-4, independent clipping. Actor weights
and log standard deviation must remain byte-identical through warmup. Save the
initial BC checkpoint after this warmup and report actual critic warmup steps
separately; none is credited as an on-policy actor update or extra PPO episode.

Starting from that exact BC checkpoint, run65536 genuine PPO environment steps
for EACH seed (196608 total), with independent actor Adam1e-5 and critic Adam
1e-4, rollout1024, minibatch128, epochs10, gamma1, GAE.95, clip.2, entropy0,
targetKL.01 and independent norm limits.5. Actor KL stopping does not stop
critic epochs. Keep every16384-step checkpoint and every final endpoint. Do
not select seeds/checkpoints from outcomes. Log true Adam steps separately
from SB3 epoch counters and from warmup/supervised updates.

The primary reward component is100 times the telescoping decrease in complete
penalized episode RMSE over120 physical50ms ticks. Failure fills every unrun
tick with6.25m². The horizon is a true terminal with a real terminal observation.
Additional terminal constraints are fixed and separately logged: heading/rate
RMS ratios above1.05 of the matched training LQR shadow cost20 per unit excess;
progress below.995 of it costs100 per unit deficit and another5 below.99;
failure costs20. Shadow truth is reward-only, absent from actor observations.
These terms mean total reward is not claimed to equal pure RMSE. The environment
is not claimed to be fully observed merely because the primary reward has a
causal running-error feature. No positive hypothetical-tail cost bonus.

After each PPO endpoint freezes, a separate continued-BC control starts from
its identical initial BC and makes exactly the same number of additional actor
optimizer minibatches as that seed's actual PPO actor updates. It uses the same
teacher dataset/weighted loss/BC rate with a separate supervised optimizer;
its actor weights never receive PPO gradients. Keep all three controls. This
comparison prevents extra supervised fitting or the shared safety repair from
being attributed to reinforcement learning.

Validation namespace2134151 generates72 new fixtures (four scenarios, speeds
8/12/16, delays0/50/100ms, both mirrors), with new continuously drawn states,
stiffness.75..1.25, road phase10..28/amplitude.9..1.3 and declared NPC shifts
and speeds as in the preceding bounded-domain studies. The final namespace
2134152 generates TWO draws per factorial cell:144 additional untouched cases.
Neither namespace is opened before all declared endpoints and controls freeze.
No validation tuning/seed selection is allowed before the final stage.

Evaluate matched LQR and adaptive/MPC once each, initial BC/continued BC/PPO
once for every seed, and one fixed causal analytic-refiner control:12 roles per
case,864 validation plus1728 final episodes. The refiner checks fixed four
signed/decaying8-coefficient profiles using the SAME owner projection and model
information; it has no learned weights or future truth. Its exact implementation
freezes before prospective evaluation and is a separate strong control.

Every trajectory uses the complete120-tick penalized score, retaining all cases,
delays, failures and seeds. Use5000 paired bootstrap draws over36 scenario/
speed/delay strata, retaining mirrors, state replicas and all seeds together;
bootstrap seeds2134153/2134154. These intervals are conditional on these three
trained policies. Report mean RMSE gain>=10% and lower95% bound>=10% separately;
the latter is needed for an inferential 'at least10%' claim. Also require
positive benefit bounds against initial BC, continued BC, analytic refiner and
other stated references, zero collision/corridor failures for every actor,
each case's progress>=99% of matched LQR, and every actor's mean heading/rate
RMS<=110% of matched LQR. No aggregate hides a single-actor safety failure.

Freeze the same policy/model hashes for actual IPC/owner50ms runtime checks,
with real sensor/source wall times and final ownership deadline rejection.
No concurrent learning during formal timing. Native vehicle interfaces are
calibrated policy-free and frozen identically for all methods before final
policy outcomes; physically independent moving traffic is required for any
collision claim. Native readiness/calibration remains separate from final
same-controller transfer. Overall qualification is false if any required
performance/safety/quality/runtime/native gate fails. Successful code/tests or
numerical replay never overrides a failed performance gate.
