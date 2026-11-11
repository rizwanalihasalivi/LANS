# Sequence-PPO evidence and promotion decision

The registered ten-percent incremental RMSE target was **not achieved**. The
optimizer correction improved the new sequence policy, but the corrected
candidate is not promoted: superiority over the strong adaptive/MPC reference
is unconfirmed, the existing scalar PPO remains slightly better on this cohort,
and progress and heading gates fail.

## Actual changes and completed experiments

The new PPO action contains eight steering-residual knots instead of one
scalar. Forty causal input features account for estimated dynamics, pending
commands, previous actions and original proposal age. An independent owner
compares the resulting two-second plan against the unchanged v8 analytical
decision. The original physical, model-uncertainty, freshness, corridor,
collision and predicted heading/rate limits are retained. Longitudinal
supervision and the other agent's shared controller are unchanged.

The training-only causal teacher probe completed 192 episodes and supplied 7680
causally reconstructed BC examples. Its 0.509052% training-only RMSE reduction
against adaptive/MPC is an analytical-search diagnostic, not a PPO result.

Original sequence training completed 32768 real PPO transitions for each seed
42/43/44, totaling 98304. Its actual saved Adam step counts were only 33/33/32:
the narrow policy distribution and actor step size repeatedly triggered KL
stopping. The manifest field `actual_ppo_updates` holds SB3's epoch counter,
which is 32 in each original run; it must not be cited as an Adam-step count.

A separate arm was registered from those training diagnostics before the
prospective outcome existed. It restarted each exact BC checkpoint and damped
only actor parameter changes by 0.01 while retaining the original critic rate,
reward, action distribution, KL threshold and controller guards. That arm
completed another 98304 actual PPO transitions, with **2560/2533/2560 actual
Adam steps**. No teacher gradient was added during PPO training. Total new PPO
transitions in this study are **196608**.

The original comparison completed 864 episodes and the registered corrected
comparison another 216: **1080 six-second episodes**, 129600 recorded control
ticks. These evaluate 72 fixtures with all declared seeds and controls; they
are not 1080 independent scenarios. The four scenarios are following, merging,
crossing and curved roads, with three speeds, three actuator delays and two
mirrored variants. No seed, checkpoint, case or delay was selected for promotion.

## Whole-run RMSE and PPO attribution

All numbers below use the complete 72-fixture prospective cohort and all three
actors. Positive gain means lower RMSE. Paired 95% confidence intervals use
5000 draws over 36 scenario/speed/delay groups, retaining mirrored variants and
all seeds in each draw.

The corrected sequence hybrid's mean episode RMSE is **0.082491341 m**:

- Against LQR, 0.086346111 m: **4.464324% lower**, CI **3.799909% to 5.114145%**.
- Against adaptive/MPC, 0.082630124 m: **0.167957% lower**, CI **-0.172284% to 0.470075%**.
- Against initial sequence BC, 0.082515359 m: **0.029108% lower**, CI **0.006132% to 0.056900%**.
- Against original sequence PPO, 0.082699780 m: **0.252044% lower**, CI **0.133456% to 0.380667%**.
- Against the existing v10 scalar PPO, 0.082417921 m: **0.089082% higher**, improvement CI **-0.499839% to 0.280327%**.
- Against the direct causal sequence search, 0.081967571 m: **0.638996% higher**, improvement CI **-1.187840% to -0.202539%**.

The positive BC comparison is evidence of a small extra benefit from the PPO
stage on this cohort. It is **0.029108%, not 10%**. The 4.464324% comparison with
LQR includes the analytical adaptive/MPC contribution and must not be attributed
entirely to PPO. The 0.167957% adaptive comparison crosses zero and does not
establish reliable superiority over the strong nonlearned controller.
The absolute BC difference is approximately **0.000024018 m (0.024 mm)**;
statistical detectability here does not establish practical significance under
sensor noise or native simulation.

The original sequence arm was 0.084299% worse than adaptive/MPC and 0.223499%
worse than its BC initialization. The correction repairs that observed
degradation, but does not establish a large new controller advantage.

## Safety, quality and authority

All 1080 prospective episodes record **zero collisions and zero corridor
failures**. This is evidence on the tested cohort, not universal safety.

The corrected hybrid's mean heading RMS is 0.013559075 rad, versus LQR's
0.012315989 rad: **10.093267% higher**. Actor 44 fails the registered 110% mean
heading threshold. Steering-rate RMS is 0.096944823 versus LQR's 0.093839979:
**3.308659% higher** (both in rad/s). Therefore the candidate does not dominate
LQR in every
metric, even though its steering-rate threshold passes.

Each corrected actor fails the per-case 99%-of-LQR progress condition. The
minimum ratio is approximately **35.53%** on a crossing fixture. The unchanged
analytical reference also loses substantial progress on that fixture, so this
is a shared-owner limitation rather than evidence that PPO alone caused it.
The failures remain disqualifying and require new matched validation after the
other controller repair is integrated.

At actuator delays 0/50/100 ms, corrected PPO's incremental mean RMSE gains
against adaptive/MPC are **0.359383% / 0.163164% / 0%**, respectively. The
selected PPO-command counts are **855 / 914 / 0** out of 8640 ticks per delay.
At 100 ms, the 50 ms service exhausts the strict 150 ms proposal-age budget.
Every neural path then reproduces the analytical fallback. These fixtures
remain in the complete mean; no age limit was relaxed to manufacture a gain.

## Evidence and limits

`README.md` explains recovery, dependencies and numerical replay. Restored
`results/ppo-plan-v11/evaluation/assessment.json` and
`results/ppo-plan-v11/damped-evaluation/assessment.json` retain complete paired
results, all three actors and every failed promotion reason. `verification.json`
records independent physical, analytical-shadow, causal-query, neural-action,
three-model admission and statistical replay. A passing replay report certifies
the record's consistency, not the candidate's ten-percent performance target.

The small positive PPO-versus-BC interval is specific to these nominal-network
fixtures. A confirmatory, untouched evaluation remains necessary after an
eligible controller is frozen. Native Webots transfer and actual runtime
deadline certification have not been established for these sequence policies.
The spawned worker has functional contract and timestamp tests only. This
branch does not replace earlier controllers or overwrite historical results.

The conditional prefix relaxation is retained as a diagnostic, with a
26.482693% optimistic maximum gain on opened training fixtures. It assumes
zero error after an unmodifiable prefix and is neither attained performance
nor a proof that ten percent is feasible or impossible under all real guards.

The completed independent audit **passed**: all 196608 PPO transitions and
complete analytical reward shadows, 1080 comparison episodes / 129600 ticks,
8454 admitted training plans and 4788 admitted comparison plans were replayed.
The separate probe replay passed 192 episodes and 550 admitted plans. Focused
functional checks finished **17/17 passing**. Training itself included
**3/1/4 terminated failures** for seeds 42/43/44 in each arm (eight per arm);
these are retained in full and are distinct from the zero failures observed on
the prospective comparison cohort. Audit success does not make those training
failures or failed promotion criteria disappear.

Further progress requires more than citing the larger optimizer count: PPO's
additional whole-run benefit must survive the strong analytical and BC controls,
and the shared progress and heading gates must pass. No ten-percent or
publication-ready superiority claim is supported by this study.
