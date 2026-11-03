# Corrected conflict timing and causal initial response: verified execution

The selected early-identification conic controller passes the original
development performance gate on the new frozen cohort: **5.185945% lower
whole-run RMSE than calibrated LQR** and **1.074249% lower than the shared
optimized nominal reference**, with positive clustered confidence intervals.
The requested **30% against all seven implemented references is not achieved**.
One actual-worker deadline miss remains. Final reserved, formal runtime promotion
and Webots evaluation are unopened under the declared 30% procedure.

This directory contains code, experiment protocols and raw evidence. It contains
no thesis draft, figure or presentation table.

## Corrections and selection

The common traffic supervisor previously returned the earlier individual
occupancy-interval start after detecting interval overlap. First simultaneous
occupancy is the later start. The corrected `conflict_time` applies to every
controller, including every reference; historical raw data remain unchanged.
In the observed v7 case, the old calculation reported immediate conflict although
the overlap began about 2.0302 seconds later. Its false emergency braking helped
cause the conic progress failure. On the seven-run known-case replay, all three
conic policies now retain 99.6144%--99.9616% of the corrected LQR's progress,
above the original 99% requirement. This is a known-failure regression check,
not independent performance evidence.

The fixed training-only study contains 576 episodes: four candidates in nominal
optimized and adaptive modes on all 64 original training fixtures, plus matched
LQR. Candidates are legacy v6, v7 conic, conic with causal early identification,
and early-identification conic with tracking-SSE admission. The original actuator,
freshness, corridor, collision and predicted heading/rate guard remain enforced.
Selection requires zero failures, actual mean heading/rate ratios <=1.10 in each
mode, every case's progress >=99%, then minimum mean RMSE with a name tie-break.

The early-identification conic wins at 0.088266668 m training mean, versus legacy
0.088367385 m. The tracking-ranked candidate is retained at 0.088267604 m and is
not substituted after seeing fresh outcomes. Early identification uses received
ego transitions and applied commands only; true stiffness never enters control.
Its empirical compatibility test is for the declared simulation observation
model, not a statistical confidence interval or a real-sensor guarantee.

## Prospective outcomes

Before prospective outcomes, the selected code and three original policy hashes
were frozen. Development uses namespace 82413000, phase 18 and amplitude 1.2;
all 32 scenario/mirror/speed/stiffness cells are included. The complete campaign
has 848 episodes, including original failure regressions, fresh communication
stress and all three legacy-hybrid endpoints. There is no checkpoint, actor,
episode or time-window selection and no new PPO training.

On the complete fresh six-second runs, mean hybrid RMSE is **0.072670438 m**;
matched LQR is **0.076645217 m**. The original gate's eight scenario/speed-cluster
bootstrap gives 95% gain intervals [3.066305%, 7.274090%] against LQR and
[0.292434%, 1.893939%] against optimized nominal control. All three hybrid actors
improve over LQR individually; the gate reports no failure reasons.

The separate all-reference analysis retains every comparison: 5.185945% versus
LQR, 5.177634% versus fixed correction, 4.354698% versus deterministic correction,
1.074249% versus optimized nominal control, 0.025772% versus adaptive-only,
4.836405% versus PPO-only and 0.596361% versus the matched legacy hybrid. Its
bootstrap uses its separately declared seed; individual intervals appear in the
raw JSON. They are not simultaneous guarantees against all possible controllers.
The very small adaptive-only comparison matters: these data do not establish
a large incremental benefit from the frozen PPO component.

All 336 hybrid regression/development/stress episodes have zero observed
collisions or corridor failures. Every fresh hybrid cell retains at least
99.7390% of matched LQR progress. Mean heading RMS is 9.0868% higher and mean
steering-rate RMS 3.6623% higher than LQR. These satisfy the original <=10%
quality limits but do not support a claim of better performance in every metric.
The 5.185945% figure comes from a different cohort than v6's 4.827%; the matched
0.596361% comparison, rather than subtracting those cohort percentages, measures
the new controller's RMSE advantage over the legacy hybrid here.

## Actual-worker timing and remaining limits

After simulation CPU jobs finished, all nine prespecified functional checks ran:
three policies crossed with nominal following, curved ego blackout and merge
worker crash. Of 1,080 ticks, one response and cycle exceed the 50 ms deadline.
Mean input-to-issue response is 11.7845 ms, p95 28.2705 ms, maximum 52.812154 ms;
maximum cycle is 53.134840 ms. Collisions and corridor exceedances are zero.
All outcomes are retained and no slow case was retried.

The miss is seed 44 nominal following, tick 98. Complete controller decision
takes 51.6302 ms; the inner legacy instrumentation reports 12.4759 ms and omits
outer planning/identification work. The full response measurement is authoritative.
The available component wall times do not identify an OS scheduling or individual
solver-stage cause. The planned proposal was not selected on this tick. Moving
expensive planning off the synchronous control path would require a new causal
controller and its own performance/latency validation; this study does not claim
that repair is complete. These finite cloud checks are not WCET evidence.

The original statistical development gate now passes. The user-requested 30%
whole-run target, zero-miss runtime and universal metric superiority do not.
Reserved cases, formal runtime promotion and native Webots remain NOT_RUN.

## Verification and recovery

All **1,431 simulation episodes / 171,720 ticks**, plus **nine functional checks /
1,080 ticks**, independently replay and verify. Coverage, source/model hashes,
RK4 physics, applied-command FIFO, physical limits, geometry, actual quality,
RMSE, fixed selection, all seven comparisons and deadline counts are checked.
All 1,431 simulations have zero recorded collision/corridor/early failures;
this does not erase quality trade-offs or the timing miss. The focused suite has
**100 passing tests**. An initial test incorrectly expected immediate uncertainty
contraction near both identification-grid boundaries; the corrected test checks
the conservative broad uncertainty there. Both test logs are retained; the
controller was not changed to force the assertion to pass.

Three archives in `evidence/` contain **3,186 members**, verified by outer SHA256,
every member SHA256 and size, and ZIP CRC. The largest is 32.13 MiB. Restore the
archives at the repository root for read-only replay; historical model/input
archives from the earlier pipeline remain dependencies. Use the recorded
Python 3.10 environment and v5 dependency pins plus Clarabel 0.9.0.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_CPP_MIN_LOG_LEVEL=2 MPLCONFIGDIR=/workspace/lans-setup/mpl
export NUMBA_CACHE_DIR=/workspace/lans-setup/numba8-cli
python -m tools.unified_control_v8.verify
python -m tools.unified_control_v8.package --verify
```

Keep pytest JIT caches separate. `calibrate`, `campaign`, `conflict_regression`
and `live` are the execution entry points; completed source-frozen studies must
not be overwritten or silently resumed with changed code. Fresh research needs
new outputs and a new declaration; verification of this saved evidence needs
no new experiments.
