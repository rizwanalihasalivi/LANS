# Frozen recovery/sensor-ablation plan

Declared before new development outcomes. Base V2V code/results at `d5cc9efd`
remain unchanged. The eight-second v1 blackout RMS of 8.140 m arose after
1.3 s of mandatory -6 m/s² braking followed by acceleration-limited recovery.
Avoiding that physical gap growth requires additional fresh knowledge, not
silently accepting stale messages or increasing actuator authority.

The one candidate is independently fresh local range/range-rate fallback with
explicit source agreement checks. The original following law, 6 m standstill
gap, 1.2 s headway, acceleration bounds, V2V TTL 0.4 s and supervisor stay fixed.
Local range TTL is 0.2 s. Both unavailable, missing ego, inconsistent fresh
sources and invalid predecessor geometry require the existing braking fallback.
All settings are engineering assumptions, not certified risk bounds.

Compare **v2v_only**, **radar_acc**, **fusion** on matched scenarios, initial
states, speed, exogenous sensor noise and communication seeds. Radar-ACC gets
the same range/rate sensor as fusion; no extra network data enters its control.
The V2V-only comparison quantifies added sensing, not improved PPO or an
equal-information controller advantage. There is no learning in this study.

Finite grid: speeds 8/12/16 m/s, three development seeds 4101/4102/4103, and eight
scenarios: nominal, leader braking, V2V blackout, radar blackout, dual blackout,
loss/jitter, ego blackout, cut-in. Each runs 20 s; three vehicles plus the
scripted cut-in vehicle when applicable. Development: 216 episodes. No parameter
search, best-seed selection or budget extension follows these outcomes.

The range model uses only relative longitudinal range/rate plus synchronized
local ego sensing, bounded errors ±0.10 m / ±0.05 m/s, 10 Hz samples and 50 ms
delivery. Range is limited to 120 m; target association is idealized. Cut-in
membership is an explicit common scenario event, not autonomous identity
recognition. Perception of non-connected traffic in arbitrary lanes remains open.

Primary checks on development AND confirmation:

1. At least 50% mean spacing-RMS reduction versus V2V-only on communication-
   blackout cells; lower seed-cluster bootstrap gain bound above zero.
2. Overall mean spacing RMS no more than 5% above radar-ACC; nominal no more
   than 10% above V2V-only (absolute allowance 0.01 m for numerical/noise scale).
3. Zero observed collision or corridor violations for fusion, intact bounds,
   and zero stale-source-use violations. This is a finite simulation check.
4. At least 99% matched V2V-only follower progress in every cell.
5. Aggregate follower jerk RMS no more than 5% above V2V-only, with an absolute
   0.1 m/s³ allowance. Emergency braking is never jerk-limited to force a pass.

Bootstrap: 5,000 fixed-seed resamples of the three independent seed clusters;
speeds within seed are correlated. Intervals are descriptive with only three
clusters, not broad road-population confidence claims.

Only if every development check passes: freeze the controller and evaluate
confirmation seeds 5101/5102/5103 on the same declared scenario classes, with
independent initial/noise draws and fault timing shifted by 0.15 s. No confirmation
outcome is used for tuning. Only if confirmation passes may the same recovery
controller proceed to a separate native local-Radar Webots check. Failure keeps
the conditional stages closed; all failures and diagnostics remain archived.

The runner records a source/protocol hash freeze before the first episode,
per-episode raw local measurements/V2V receipts/commands/true scoring states,
an independent receiver/control/physics replay, per-seed summaries and all gate
decisions. Existing main-controller reserved data remain untouched.
