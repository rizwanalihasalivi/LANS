# Four outstanding v8 issues: development work

Acceptance remains open. The target is at least5% fresh matched RMSE gain,
every-case progress of at least99%, no mean heading/rate regression, and zero
observed strict50ms response/full-cycle misses. Fresh final evaluation stays
closed while development misses these joint requirements. No PPO policy,
reward, training schedule or17-feature contract is changed here.

The default controller keeps its existing law. New controller candidates remain
experimental; only command-equivalent scalar operations and the reusable native
step interface affect shared code. `RESULTS.json` records all open gates. The
aligned512-record calibration's quality-eligible half-feedback arm gives0.280%
RMSE gain, heading0.996 and steering-rate0.999 of LQR; it misses5%. The original
case-progress regressions pass in development, but require independent component
validation. There is no successful replacement/fresh-final result to announce.

`longitudinal.py` replaces discontinuous acceleration selection with a bounded
scalar barrier projection using received information. The7 exposed regression
fixtures, all current comparators and3 original actors produced154 development
episodes. Selected frequency3 has zero hybrid failures and minimum matched
progress99.9611%. This is finite exposed development evidence.

`fast_kernels.py` removes RK4 allocation overhead with the same equations/order.
Tests compare random low/high-speed steps, every rollout score/margin and actual
closed-loop commands. Shared scalar clipping also preserves the old constraints
and NaN rejection while avoiding NumPy's scalar-array dispatch. Native Driver
steps can use an equivalent C call loop; every1ms actuator/sensor/physics call is
retained and compared against the Python implementation with a stub API.

`committed.py` fixes asynchronous proposal alignment: submit after command issue,
forecast the committed service prefix, retain the real original observation
timestamp and apply the unchanged150ms freshness boundary. `aligned.py` tests
that mechanism with the original v8 proposal law and explicit feedback weights.

Preview, strict Pareto, curvature-dynamics and scheduling attempts retain all
their outcomes. Several improve tracking while raising quality costs; others
remove quality regressions but miss5%. The576-record strict Pareto development
selected a2s setting with only0.162% adaptive gain. The known-model oracle
diagnostic is explicitly nondeployable and gives no impossibility/safety proof.

Actual Webots timing probes retain their fixed releases, complete-cycle trace
flush and1ms vehicle integration. Native results concern single-vehicle transfer
with ideal supervisor sensors. They provide no native traffic-collision proof,
real-world guarantee or universal worst-case execution-time bound. GUI/CPU/GC
and C-loop variants have shown remaining misses; none establishes timing closure.

Use `/workspace/lans-setup/env.sh` in this environment, or equivalent pinned
dependencies. Run `python -m pytest -q tools/v8_four_gates` from the repository
root. Probe entry points require new output directories and refuse to overwrite
evidence. Read each recorded plan/source snapshot before reproducing a campaign.
Independent audits reconstruct scalar dynamics, wire arrivals, FIFO and scores;
native audits check recorded frame/timing/sample consistency. Failed gates and
interrupted attempts remain part of the evidence.

The sealed archive contains9,582 files (638,201,227 raw bytes) in13 bounded ZIPs.
Run `python -m tools.v8_four_gates.seal --verify` to check its exact inventory.
The relevant control suite passed149 tests, and2 separate archive-integrity
checks passed. All1,242 full Python development episodes and22 native experiments
passed their independent record/dynamics checks; scientific gate failures are
retained separately from record-integrity success.
