---
title: "Latency-Aware Residual Vehicle Path Tracking with Predictive Runtime Supervision"
author: "Rizwan Ali — Supervisor: Jie Tian"
date: "Research revision: 27 October 2026"
---

**Nanjing Forestry University — Master's Thesis Opening Report (revised research draft)**

Student number: __________. Official major: __________.

This revision records the agreed residual-control study and its new evidence.
It does not certify the original manuscript's numerical claims or constitute a
submission-ready report. Bibliography verification and the scientific gaps below
remain open.

# 1. Background and research question

Learned vehicle controllers must operate within physical and timing limits. A
small neural network can compute quickly, yet its command can be old because of
dispatch, scheduling, communication or a blocked worker. A useful proposal can
therefore become inappropriate before application. Conversely, freshness alone
does not establish that a learned correction improves a strong analytical tracker.

LANS studies an independently executing LQR baseline augmented by a bounded PPO
residual. A predictive supervisor admits assistance only after freshness,
validity, operating-envelope and predicted-benefit checks. PPO does not replace
the full steering controller in this study. Full-command PPO/LQR switching is a
different experiment and is not validated by these results.

The central question is: **can causal PPO residual assistance earn useful authority
over a strong LQR baseline, outperform matched nonlearned corrections, and preserve
baseline behavior when learned proposals are delayed, unavailable or unhelpful?**

# 2. Related research and comparative position

| Primary supplied work | Relevant established capability | Implication for LANS |
|---|---|---|
| Wabersich and Zeilinger [1] | Predictive safety filtering with model uncertainty and backup plans | Predictive filtering is established. LANS's nominal performance check is not an equivalent safety certificate. |
| Tearle et al. [2] | Learned racing-controller filtering and a physical miniature vehicle demonstration | Vehicle supervision and backup trajectories already exist; LANS lacks equivalent physical evidence. |
| Cano Cordoba et al. [3] | Formal shielding under delayed observations and CARLA experiments | Delay-aware supervision is established; observation delay differs from learned-worker availability. |
| Kalaria et al. [4] | Computation/actuator delay estimation and robust driving/racing control | Closest application overlap; residual rejection differs from active robust delay compensation. |
| Tabrizian et al. [5] | Delay-aware learning for merging with stochastic V2I observations and fallback | Different task and delay mechanism; merging success cannot be ranked against path-tracking RMSE. |

Simplex/runtime-assurance architectures already combine advanced control, backup
control and supervisory decisions. Residual reinforcement learning is likewise
established. Their combination is not proof of a new algorithm. The candidate
contribution is explicit causal execution, predictive residual authority and
auditable attribution under declared vehicle conditions. The term neuro-symbolic
refers here to a neural proposal and explicit runtime predicates/states; a strong
logic-reasoning or first-of-kind claim has not been established.

The five supplied PDFs support primary-text comparison of those versions.
Publisher metadata, a broader search and matched published-method reproduction
are incomplete; no superiority to those papers is claimed.

# 3. Research objectives

1. Establish consistent coordinates, estimation, steering units, actuator limits
   and packet semantics across all controllers.
2. Implement causal PPO training/runtime inputs without pending-result or
   completion-time leakage.
3. Evaluate incremental learning against LQR, supervised initialization and
   same-supervisor fixed residuals.
4. Specify and test predictive authority, stale rejection and recovery rules.
5. Measure lateral accuracy alongside heading error, steering activity and survival.
6. Distinguish actor duration, action age, IPC/queueing and local-loop deadlines.
7. Preserve failed outcomes and conditional test boundaries; assess native and
   physical transfer separately.

# 4. Proposed method

## 4.1 Signal flow and authority

| Block | Input and role | Output |
|---|---|---|
| State/reference interface | Noisy measurements, estimator and known reference map | Estimated state, measured speed, curvature previews and actual steering |
| Independent LQR | Fresh available local state and frozen nominal model | Baseline steering |
| Observation Builder | Physical features and observable execution history | Normalized causal policy input |
| Asynchronous PPO | Bounded categorical residual policy | Residual packet retaining its observation timestamp |
| Latency/Execution Monitor | Request, computation, arrival and application timestamps/status | Computation duration, packet age and worker status |
| Predictive supervisor | Valid packet, local state, baseline and nominal prediction | Selected residual and authority weight |
| Fusion/actuator | Baseline plus weighted residual | Constrained steering command and actual actuator response |

The command is

\[
\delta_{\mathrm{cmd},t}=\operatorname{sat}_{[-0.5,0.5]}
\left(\delta_{\mathrm{LQR},t}+w_t\Delta\delta_{\mathrm{sel},t}\right).
\]

The selected residual is unweighted; fusion applies $w_t$ exactly once. Rejection
sets $w_t=0$. Baseline and hybrid share identical actuator constraints. Independent
execution is a design requirement whose actual timing must be measured.

## 4.2 Vehicle and actuator model

The nonlinear bicycle plant has state $[X,Y,\psi,v_y,r,\delta_a]^\top$ and prescribed
longitudinal speed $v_x$. Its equations are

\[
\dot X=v_x\cos\psi-v_y\sin\psi,\quad
\dot Y=v_x\sin\psi+v_y\cos\psi,\quad \dot\psi=r,
\]

\[
m\dot v_y=F_{yf}\cos\delta_a+F_{yr}-mv_xr,\qquad
I_z\dot r=l_fF_{yf}\cos\delta_a-l_rF_{yr}.
\]

Tire inputs are $\alpha_f=\delta_a-\operatorname{atan2}(v_y+l_fr,v_x)$ and
$\alpha_r=-\operatorname{atan2}(v_y-l_rr,v_x)$. The Fiala law uses $z=\tan\alpha$:

\[
F_y=\begin{cases}
Cz-\dfrac{C^2}{3\mu F_z}|z|z+\dfrac{C^3}{27\mu^2F_z^2}z^3,
& |z|<3\mu F_z/C,\\
\mu F_z\operatorname{sgn}(z),&\text{otherwise}.
\end{cases}
\]

Nominal parameters are $m=1650$kg, $I_z=4224$kg m$^2$, $l_f=1.2$m,
$l_r=1.4$m and $C_f=C_r=80000$N/rad. Static axle loads follow the nominal geometry.
The mismatch condition scales both cornering stiffnesses to70%; it is not a mass
variation experiment. RK4 advances the plant at1ms with a10ms control period.

\[
\dot\delta_a=\operatorname{clip}
\left((\delta_{\mathrm{cmd}}-\delta_a)/0.05,-0.35,0.35\right).
\]

Command and actuator angles are limited to0.5rad. Longitudinal control, obstacles,
full localization and physical vehicle validation are outside this steering model.

## 4.3 Coordinates, sensing and LQR

The implementation defines $e_y=Y-Y_{\mathrm{ref}}(X)$ and
$e_\varphi=\psi-\psi_{\mathrm{ref}}(X)$; this is not exact Frenet projection.
The internal feedback state is $x_e=[e_y,v_y,e_\varphi,r]^\top$. A rate-state paper
notation requires the small-angle relations
$\dot e_y\approx v_y+v_xe_\varphi$ and $\dot e_\varphi\approx r-v_x\kappa$.
These vectors cannot simply be renamed without transforming the model/gains.

A Kalman estimator uses noisy lateral error, heading error and yaw rate; measured
speed is noisy as well. Nominal standard deviations are0.03m,0.17degrees,
0.01rad/s and0.1m/s. Map station/reference preview is assumed available in the
simulation; it is not a validated localization pipeline.

The LQR has $Q=\operatorname{diag}(4,0.1,8,0.2)$ and $R=100$, with frozen15/20/25m/s
gains interpolated in speed and nominal curved-path equilibrium/feedforward:

\[
\delta_{\mathrm{LQR}}=\delta_{\mathrm{ff}}-K(v_x)(\hat x_e-x_{e,\mathrm{ref}}).
\]

## 4.4 Causal residual policy

The actor has20 channels, two64-unit tanh layers and five categorical logits.
Actions map to $\{-0.08,-0.04,0,0.04,0.08\}$rad. Physical features include estimated
tracking quantities, measured speed, actual steering and curvature at0/10/20m.
Observable history includes prior authority, recovery state, held-packet residual,
held age and last command. Five pending/forecast/service-oracle channels remain
constant zero in training and runtime. No current calculation's future duration
is provided as an input.

One request is in flight. A ready packet is delivered before the next observation;
its original timestamp is retained. While the worker is busy, new sampled actions
are not submitted. The local loop continues advancing the plant and selecting a
command. Real spawned-worker timing and simulated service schedules are distinct.

## 4.5 Predictive symbolic supervisor

Eligibility requires finite data, valid sequence, nonfuture packet age below50ms,
$|\hat e_y|\leq1.5$m and $|\hat e_\varphi|\leq0.25$rad. These checks define an
experimental operating envelope, not a certified recoverable set.

The nominal predictor compares LQR-only and bounded residual candidates over200ms.
Each candidate is held for50ms before returning to the same LQR continuation.
Curvature is held locally constant; actuator lag/rate limits are represented.
Stage costs include normalized lateral, heading and yaw-rate error, steering
effort and command movement; the exact weights are frozen in executable source
and protocol. A terminal lateral/heading cost is included.

\[
J(w)\leq J(0)-\max(10^{-7},0.01J(0))
\]

is required before admission. Candidate caps are0.1/0.25/0.5, age-adjusted, with
authority increases at most0.05 per tick. Three favourable control ticks provide
admission persistence; they may evaluate the same held packet and are not three
independent fresh responses. Stale/invalid proposals revoke authority immediately.
Prediction is nominal and can disagree with actual nonlinear performance.

## 4.6 Reward and optimization

Training uses the executed command rather than an unconstrained proposal:

\[
r_t=-\left(\frac{e_y}{0.5}\right)^2
-0.2\left(\frac{e_\varphi}{0.1}\right)^2
-0.005\left(\frac{\delta_{\mathrm{cmd}}}{0.5}\right)^2
-0.001\left(\frac{\delta_{\mathrm{cmd}}-\delta_{\mathrm{prev}}}{0.005}\right)^2
-10\mathbf{1}_{\mathrm{failure}}.
\]

No exogenous computation-delay penalty or privileged counterfactual reward is
used. An independent random latency penalty does not establish learned faster
CPU execution. PPO uses learning rate$10^{-4}$, clip0.1, target KL0.01,
$\gamma=0.99$, GAE0.95, batch200, five epochs and four250-step environments.
Three scratch and three supervised-initialized pilots each receive25,000 extra
steps. The causal student's pretraining is extra budget, explicitly reported.
Normalization is frozen from its training data, not fitted to evaluation cases.

# 5. Experimental design and proposed contributions

The development design uses three training/noise blocks,15/25m/s, two known paths,
two physically mirrored signs and four conditions: nominal, tire mismatch,
20ms service and100ms service. Nine methods produce864 episodes. Initial signed
errors and canonical measurement noise mirror consistently. Ticks and mirrored
cases are not independent training seeds.

Comparators are LQR, fixed positive/negative residuals through the same supervisor,
causal supervised initialization, scratch/fine-tuned PPO, fixed authority,
manuscript-inspired latency gain and no-recovery persistence. The latency-gain
arm is a disclosed reconstruction with common authority/stale limits; it is not
an exact published-controller reproduction or every original-paper ablation.

Primary outcome is mean episode failure-penalized lateral RMSE, with unexecuted
failed tails filled at2.5m. True heading RMSE, steering-rate RMS, total steering
movement, envelope survival, authority and timing are reported. Candidate promotion
requires at least1% improvement over LQR, student and both constants, positive
student gains in all three seed blocks, no survival loss, bounded nominal
degradation and heading/rate tradeoffs no more than5% above LQR.

Reserved confirmation uses new noise and held-out sine parameters only after
eligibility. It is not opened to rescue a failed development result. Native
Webots and actual process timing are separate evidence campaigns. The intended
contribution is causal execution and matched attribution, subject to comparison
with prior work; a positive learning result or algorithmic novelty is not assumed.

# 6. Current verified results

| Method | Lateral RMSE (m) | Gain versus LQR | Heading RMSE (rad) | Steering-rate RMS (rad/s) | Survival |
|---|---:|---:|---:|---:|---:|
| lqr | 0.090578 | 0.000% | 0.020024 | 0.069169 | 96/96 |
| fixed_negative | 0.093213 | -2.909% | 0.020279 | 0.069490 | 96/96 |
| fixed_positive | 0.093213 | -2.909% | 0.020279 | 0.069490 | 96/96 |
| student | 0.090599 | -0.024% | 0.020027 | 0.069213 | 96/96 |
| scratch | 0.092441 | -2.057% | 0.020218 | 0.069551 | 96/96 |
| finetune | 0.090618 | -0.044% | 0.020029 | 0.069243 | 96/96 |
| fixed_authority | 0.099658 | -10.024% | 0.022049 | 0.147717 | 95/96 |
| latency_gain | 0.085469 | 5.640% | 0.020310 | 0.120488 | 96/96 |
| no_recovery | 0.090637 | -0.066% | 0.020032 | 0.069265 | 96/96 |

Development eligibility: **False**. finetune lacks >=1% improvement vs lqr; finetune lacks >=1% improvement vs student; pair0 does not improve student; pair1 does not improve student; pair2 does not improve student.

Actual-worker campaign: 10500 ticks, 985 deadline misses (9.381%), functional pass:True. Learned authority was active on 0 ticks; this provides no real-worker learning-benefit evidence.

Native interface verification:True; observed native wall timing:False. Resource-partition diagnostic functional pass:True; observed timing pass:False. Partitioned generated load does not exclude host OS activity, replace original failures or establish WCET.

See the frozen protocol, raw traces, independent audits and completion-matrix.md. Reserved confirmation remains unopened when development fails.

The manuscript-inspired latency-gain comparator reduces lateral RMSE by 5.640%, but increases heading RMSE by 1.428% and steering-rate RMS by 74.192%. This exceeds the predefined5% smoothness tradeoff limit. Fixed authority loses one episode under20ms service. The simple gain is a promising descriptive tracking result, not a selected balanced winner. Same-gain student/constant controls and separate native/timing validation would be needed to attribute its benefit to additional PPO learning. The proposed predictive supervisor did not retain that tracking gain; no post-result gate tuning or reserved-test opening was performed.


# 7. Stability and claim boundaries

For an assumed delay-free unsaturated nominal linear closed loop $A_c$ that is
Hurwitz, choose $P>0$ satisfying $A_c^TP+PA_c=-Q_c$, $Q_c>0$. For a bounded matched
input $d$ in $\dot x=A_cx+Bd$, the quadratic function $V=x^TPx$ satisfies

\[
\dot V\leq-\frac{\lambda_{\min}(Q_c)}{2}\|x\|^2+
\frac{2\|PB\|^2}{\lambda_{\min}(Q_c)}\|d\|^2.
\]

This conditional bound does not imply zero convergence under nonzero residuals,
nor global safety for nonlinear tires, saturation, estimation, sampled feedback,
varying speed or delayed execution. Numerical augmented-model checks are limited
to their stated linear assumptions. LQR fallback does not recover every state.

Long PPO unavailability with fresh local sensing is different from delayed LQR
feedback. Actor p99 is not WCET; reciprocal inference time is not closed-loop
frequency. The original49x speedup, GPU energy ratio, broad generalization,
strictly greater-than200ms delay bound and global stability claims are withdrawn
from this revised evidence draft.

# 8. Remaining research and submission requirements

Failed learning criteria require mechanism diagnosis and a separately frozen new
hypothesis before further training. They do not justify selecting on reserved
cases or extending a budget until improvement appears. The source/queue contract,
paired metrics and negative evidence should be retained.

Remaining items include a matched feasible published-method reproduction,
complete reference metadata, any missing factor-isolated ablations, unresolved
local deadline behavior and actual target-hardware measurements. Real-vehicle
readiness requires physical sensing/communication/actuator evidence; a laptop
actor benchmark is not a substitute. The report remains a research draft.

# References

[1] K. P. Wabersich and M. N. Zeilinger, "A predictive safety filter for learning-based
control of constrained nonlinear dynamical systems," supplied arXiv:1812.05506v4,2021.

[2] B. Tearle, K. P. Wabersich, A. Carron and M. N. Zeilinger, "A predictive safety
filter for learning-based racing control," supplied arXiv:2102.11907v1,2021.

[3] F. Cano Cordoba, A. Palmisano, M. Fraenzle, R. Bloem and B. Koenighofer,
"Safety Shielding under Delayed Observation," supplied ICAPS2023 proceedings.

[4] D. Kalaria, Q. Lin and J. M. Dolan, "Delay-aware Robust Control for Safe
Autonomous Driving and Racing," supplied arXiv:2208.13856v1,2022.

[5] A. Tabrizian, Z. Huang, A. Aziz and P. Wei, "Delay-Aware Reinforcement Learning
for Highway On-Ramp Merging under Stochastic Communication Latency," supplied
arXiv:2403.11852v5,2026.

These identify the uploaded primary versions. Final publisher metadata, additional
foundational references and a consistent complete bibliography must be verified
before institutional or journal submission.
