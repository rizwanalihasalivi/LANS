# Formation recovery v3: pre-outcome protocol

Base: `43679a5b`. V1/v2 sources, results and source freezes remain unchanged.
Dual-sensor blindness still requires maximum braking; this stage targets
recovery AFTER valid knowledge returns. Cut-in/out changes the reference gap
abruptly and saturated acceleration bounds limit how fast it can be restored.
Neither stale-packet acceptance nor a stop-to-reduce-score shortcut is permitted.

One candidate, derived before new outcomes: nominal critically damped feedback
with omega=0.8 /s, kp=omega²=0.64, kv=2*omega-1.2*omega²=0.832. Compare with
v2 fusion kp=0.35/kv=0.9. Both use exactly the same sensing/arbitration, nominal
1.2 s headway, 6 m gap, supervisor, timestamps, rejection rules and [-6,2.5] m/s²
limits. Both get the same explicit follower speed envelope cruise+8 m/s; leaders
remain capped at cruise. The nominal linear pole calculation is NOT a delayed,
saturated, nonlinear or string-stability theorem. No numerical gain search,
learning, best-seed selection or post-result threshold changes are allowed.

Reuse the eight v2 scenario classes and physically identical sensor/fault model.
Use NEW development seeds 6101/6102/6103 and NEW confirmation seeds 7101/7102/7103,
speeds 8/12/16 m/s. Confirmation shifts faults and membership events by 0.15 s.
Two methods x eight scenarios x three speeds x three seeds = 144 episodes/stage.
Episodes extend to 30 s to observe recovery; FIRST-20-SECOND error/progress is
reported separately so longer observation cannot manufacture an RMS improvement.
Cut-in membership remains a common explicit scenario command, not autonomous
recognition. The same old source code supplies sensing, plant and raw scoring.

Primary gates in BOTH stages:

1. At least 20% mean settling-time reduction for dual blackout and cut-out,
   independently, with descriptive lower seed-cluster bootstrap bound >0.
   Settling means both followers' absolute fixed-headway error <=1 m, continuously
   for at least 2 s AND with no later violation in that event segment. Fresh
   source knowledge is also required. Dual recovery starts at fault end;
   cut-out recovery starts at the declared handover. Candidate must not remain
   censored at 30 s. Baseline censoring is reported as a lower bound.
2. First-20-second spacing RMS for dual blackout and cut-in/out no more than
   5% above baseline; nominal <=10% above baseline plus 0.01 m absolute allowance.
3. Zero candidate observed collision/corridor, stale-source, blind-brake,
   actuator/steering-rate or speed-envelope violations. Braking during absent
   knowledge remains -6 m/s²; no jerk limiter may override it.
4. At least 99% matched baseline follower progress per cell, both first 20 s
   and full 30 s. Aggregate command-jerk RMS <=1.05*baseline+0.1 m/s³.

Bootstrap: 5,000 fixed-seed resamples of three independent seed clusters,
averaging correlated speed variants inside each seed. Report small-cluster
limitations, all outcomes, fixed-first-20 RMS, maximum speeds and minimum gaps.
Each case must replay receiver/controller/physics and pass independent scoring.
Parallelism is execution-only; two exact raw-hash repeats must agree first.

Only if development passes may the fresh confirmation grid open. Only if
confirmation also passes may a native factorial check open: two feedback laws
x two speed adapters (old 8 m/s cap vs follower cruise+8 recovery cap) x four
nominal/V2V/radar/dual-blackout cases = 16 native runs, 30 s each, world seed 42.
Native caps are compared separately: a gain from correcting the adapter must
not be attributed to feedback gains. Use unchanged native Radar/radio setup,
steering and acceleration limits. Require movement, source/control replay,
intact setpoint/actuator constraints and positive conservative gap proxies;
report physical speed and formation error rather than assume Python transfer.
No main unified PPO reserved data or training is opened by this study.
