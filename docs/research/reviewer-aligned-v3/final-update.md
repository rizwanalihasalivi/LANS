# Execution-aligned predictive PPO development study

27 October 2026. Frozen single supervisor/reward variant; old evidence unchanged. No post-outcome tuning or reserved evaluation.

| Source | Tracking gain vs LQR | Heading change | Actuator-rate change | Survival |
|---|---:|---:|---:|---:|
| LQR | +0.000% | +0.00% | +0.00% | 96/96 |
| negative | +0.653% | -2.28% | +2.22% | 96/96 |
| positive | +0.653% | -2.28% | +2.22% | 96/96 |
| student | +1.117% | -0.14% | +2.03% | 96/96 |
| Old PPO | +1.151% | -0.16% | +2.05% | 96/96 |
| New PPO | +1.445% | -0.27% | +2.66% | 96/96 |

Eligible: False. Reasons: lacks 1% gain vs student; lacks 1% gain vs negative; lacks 1% gain vs positive

All methods share the new supervisor, actuator, observer and causal 20-channel contract. Student is original supervised initialization, oldppo is the old 25,000 endpoint, ppo is the new prespecified 100,000 endpoint (or explicitly ineligible futility stop). Extra supervised pretraining is disclosed. Training reward measures actual actuator rate. The 1 s predictor assumes repeated proposals under healthy worker service for performance estimation; no future completion oracle enters the policy, and this is not a safety certificate.

Three training/noise pairs are small-sample development evidence; control ticks are not independent experiments. Physical readiness and hard real-time execution require separate evidence. No failed test is relabeled as a pass.


## Observed timing and scheduling diagnosis

Timing is deliberately run after training/development have finished. It uses the old fixed age_filtered diagnostic and old 25,000 PPO actors, not the new controller. Thus it isolates scheduling choices; a positive outcome cannot certify the new controller. Both profiles use the two highest available CPUs, nice 19 workers/stress and original 10 ms deadlines. The dedicated-spin profile burns one CPU and is not the laptop default.

| Profile | Missed deadlines | Functional/raw replay | Actual nonzero correction ticks |
|---|---:|---|---:|
| Sleep + 100 µs spin | 717/6000 | True | 1951 |
| Full spin | 694/6000 | True | 1870 |

| Study/profile | Misses | Already >=10 ms late at release | Wall control >=10 ms | Thread CPU control >=10 ms |
|---|---:|---:|---:|---:|
| v2 sleep | 687 | 672 | 33 | 33 |
| v2 absolute | 305 | 296 | 22 | 21 |
| v3 sleep + spin | 717 | 699 | 32 | 31 |
| v3 full spin | 694 | 669 | 37 | 36 |

Categories overlap. Elapsed control time minus thread CPU time includes descheduling, blocking, IPC and measurement-boundary differences; it is not an exact OS-only attribution. Cgroup quota, host tasks and preemption remain uncontrolled. Any miss fails strict observed timing. Finite zero misses would still not establish WCET, PREEMPT_RT behaviour, physical end-to-end latency or guaranteed 100 Hz.

## Work completed and outstanding

- Completed: one prespecified execution-aligned controller/reward study, all pilot/futility endpoints, matched same-supervisor controls, independent raw reward/filter/fusion/model replay, and isolated-from-training scheduling experiment. Failed outcomes remain published.
- New learned candidate development eligibility: **False**. See decision.json for every criterion.
- Reserved/unseen tests remain unopened unless eligibility and a separately frozen corresponding-controller timing requirement both pass. Native selected-winner confirmation follows that gate; historical native interface tests are not new-controller validation.
- The existing Python 3.10 full-controller kit remains a verified old-controller development diagnostic. No new-controller laptop deployment is claimed. Actual Windows/macOS execution requires the user laptop; physical sensors/communication/actuators require connected hardware.
- The prior nominal Eq 5/Algorithm 1 safety-filter specialization remains the scoped published comparator. Reproduction of the full robust algorithm/authors code and complete publisher metadata remain unverified; no literature-superiority claim.
- Original reviewer corrections remain: no exogenous latency reward, real queued worker unavailability, fresh LQR distinct from delayed PPO, no 49 x speedup, no fabricated ablation frequency, no global stability proof, no energy/blind-distance advantage, full disclosure of negative results and limited generalization.
- This is an evidence report, not an accepted-performance or submission-ready declaration. Additional variants require a new frozen study; thresholds are never changed to relabel a failure.

Reproduce/resume: `python tools/reviewer_v3/run3.py --publish`. Protocol, frozen sources/model hashes, training progress, complete raw traces and decision files accompany this report.

## Portable aligned-controller package and verified references

The new Python 3.10 kit now includes the actual v3 endpoint actors and the same aligned supervisor, not the old 25,000 diagnostic. Torch-to-NumPy class parity is checked on all 24,300 archived DEV observations per actor; this is export parity, not a new performance evaluation. It is a research diagnostic irrespective of selection outcome.

Clean Linux smoke uses five 3-second cases with seed 701; all three actors undergo export/golden checks. See kit-smoke/verification.json. Smoke functionality does not certify strict timing or target Windows/macOS behaviour. Actual target laptop measurements remain pending. Request/response identity and original timestamps are checked at receipt.

Run the extracted kit using RUN_WINDOWS.cmd or `bash RUN_MAC.command`; return laptop-results/Results.zip. No physical readiness is claimed.

### Simulation-to-worker timing boundary

Offline zero-service simulation can deliver a proposal in the same control tick. A separate worker polled once per 10 ms loop normally delivers on a later tick. The retained original age-gain is steep: the 0.25 cap becomes about 0.00458 at 10 ms observation age, even for fast inference. Identical supervisor code therefore does not establish identical effective authority under different delivery timing. Packet age, inference duration, post-inference service delay and loop release lateness must remain separate. This new study does not establish that the residual tracking gains transfer to a real asynchronous deployment. The kit records actual timestamps/authority for this boundary; neither packet freshness nor functional fallback is proof of physical timing safety.

# Version-specific primary-source bibliography

Verified against the five PDFs supplied by the author, not inferred publisher
metadata or search snippets. Preprints are cited as the actual supplied versions;
no unverified journal year, volume, DOI or publication status is added. This
completes these five reference entries, not a systematic literature search or an
audit of every citation in the original manuscript.

1. B. Tearle, K. P. Wabersich, A. Carron, and M. N. Zeilinger, “A predictive safety
   filter for learning-based racing control, ” arXiv:2102.11907v1, 23 February 2021.
   Title, authors, identifier and date appear on the supplied first page.
2. F. Cano Córdoba, A. Palmisano, M. Fränzle, R. Bloem, and B. Könighofer,
   “Safety Shielding under Delayed Observation, ” in *Proceedings of the
   Thirty-Third International Conference on Automated Planning and Scheduling
   (ICAPS 2023)*, pp. 80–85, 2023. Conference title/year are in the first-page
   header; the supplied six-page proceedings article has page numbers 80–85.
3. K. P. Wabersich and M. N. Zeilinger, “A predictive safety filter for
   learning-based control of constrained nonlinear dynamical systems, ”
   arXiv:1812.05506v4, 17 May 2021. This is the version used for the disclosed
   nominal Eq. (5)/Algorithm 1 specialization in reviewer-followup-v2.
4. D. Kalaria, Q. Lin, and J. M. Dolan, “Delay-aware Robust Control for Safe
   Autonomous Driving and Racing, ” arXiv:2208.13856v1, 29 August 2022. The supplied
   masthead says *IEEE Transactions on Intelligent Vehicles*, not *IEEE
   Transactions on Control Systems Technology*. It does not independently verify
   final volume/year/DOI; the citation therefore uses the verified arXiv version.
5. A. Tabrizian, Z. Huang, A. Aziz, and P. Wei, “Delay-Aware Reinforcement Learning
   for Highway On-Ramp Merging under Stochastic Communication Latency, ”
   arXiv:2403.11852v5, 27 May 2026. The supplied version reports DAROM; results or
   titles from an older version must not be silently substituted.

## What their results establish relative to LANS

| Reference | Primary evidence relevant to LANS | Comparison boundary |
|---|---|---|
|1| Predictive filtering, backup trajectories, an 80 Hz implementation and 1:28-scale physical vehicle experiments | Stronger physical/formal evidence than current LANS; its rate is not an inference-speed comparison |
|2| Safety games/shielding under delayed observations, including CARLA examples | Observation delay differs from delayed PPO-worker availability with fresh local sensing |
|3| Predictive safety filtering with backup/terminal constructions and uncertainty treatment | LANS has only a disclosed nominal specialization; its uncertified LQR fallback is not their theorem |
|4| Vehicle computation/actuator-delay handling, robust control and learned-command guarding | Close application overlap; LANS cannot claim that delay-aware supervision itself is new |
|5| SUMO on-ramp merging, delay-aware encoding and physics-based fallback;99.80% success in the reported high-density 2 s communication-delay condition | Different task, algorithm and delay mechanism; this percentage cannot rank against LANS tracking RMSE |

No one of these numerical results ranks LANS as “#1.” A matched implementation,
common task/plant, sensing and actuator assumptions, compute resource, training
budget, seeds and delay mechanism would be required. Formal guarantees also
cannot be compared using empirical survival alone. These verified entries should
replace inconsistent metadata for these five works in a revised bibliography.

## Claims that still require evidence

- Reproduction of the complete robust published algorithms/authors code.
- A broader up-to-date prior-art search, including original residual-RL and
  Simplex/runtime-assurance primary references.
- Any claimed novelty, formal safety, physical readiness or universal ranking.
- Every other entry and in-text citation in the original manuscript.

Full uploaded PDFs are not republished in this repository.


## Exact aligned method and objectives

The architecture remains LQR plus a bounded PPO residual. The vehicle feedback
and local LQR are independent of learned-worker completion by design; timely
execution still requires measurement. This is not full-command PPO/LQR switching.

For a valid held packet, the causal residual filter is

$$
f_t=f_{t-1}+\left(1-e^{-T/0.3}\right)
\left[\operatorname{clip}(\Delta\delta_t, -0.08,0.08)-f_{t-1}\right],
\qquad T=0.01\;\mathrm{s}.
$$

The candidate authority uses the retained age-gain and a ramp:

$$
\bar w_t=\min\!\left\{0.25 e^{-0.8\max(0,1000 a_t-5)}, \;w_{t-1}+0.05\right\},
\qquad a_t=t-t_{\mathrm{observation}}.
$$

Packet eligibility requires finite data, non-regressing sequence, nonnegative
age below 50 ms, lateral estimated error within 1.5 m and heading error within 0.25 rad.
An invalid/stale packet immediately clears filter, authority and recovery count.
A performance rejection retains the valid causal filter history while returning
authority to zero. Three consecutive good control ticks are required for
admission; they are not necessarily three distinct worker responses.

The nominal linear-bicycle/actuator predictor has 100 steps of 10 ms each, observable
curvature previews at 0/10/20 m,0.05 s actuator lag and 0.35 rad/s actuator-rate limit.
It compares LQR continuation with a repeated-current-residual/filter trajectory.
It admits the candidate only when

$$
J_0-J_1\geq\max(10^{-7},0.001 J_0).
$$

Each predictive stage uses lateral error, heading error, actual predicted
actuator rate and steering effort with weights 1,0.2,0.2,0.005 and normalizers
0.5 m,0.1 rad,0.35 rad/s,0.5 rad. The assumed continued healthy service is only a
performance-prediction assumption; no future completion forecast enters the
policy, and the predictor is not a robust safety certificate.

The applied steering command is

$$
\delta_{\mathrm{cmd}, t}
=\operatorname{clip}\!\left(\delta_{\mathrm{LQR}, t}+w_t f_t, -0.5,0.5\right).
$$

Training uses the actual executed transition reward

$$
r_t=-\left(\frac{e_{y, t}}{0.5}\right)^2
-0.2\left(\frac{e_{\varphi, t}}{0.1}\right)^2
-0.2\left(\frac{\dot\delta_{a, t}}{0.35}\right)^2
-0.005\left(\frac{\delta_{\mathrm{cmd}, t}}{0.5}\right)^2
-10\, \mathbf{1}_{\mathrm{failure}}.
$$

This removes the old raw command-jump penalty in this newly frozen variant.
There is no reward penalty for exogenous worker latency. The learner can change
driving actions, not the injected computation/service delay. Training reward is
not itself a guarantee that the separate development criteria will pass.

The five categorical residuals are−0.08, −0.04,0, +0.04, +0.08 rad. The actor has two
64-unit tanh layers, frozen original TRAIN normalization and three independent
PPO seeds, each with exactly 100,000 additional transitions. Original supervised
pretraining is extra and disclosed. Endpoints, not best intermediate scores, are
evaluated. Complete optimizer/rollout settings are in the frozen protocol.

The 20-channel policy interface includes estimated lateral/heading errors,
estimated lateral-error derivative, yaw rate, measured speed, actuator angle,
curvature previews, held-packet history and prior command/authority. The five
previously removed future/oracle channels remain zero. Causality does not prove
full observability: the internal residual-filter state is not a separate policy
feature, so a fully Markov policy-state claim is not made.

All methods share sensing, actuator and supervisor settings in the matched
comparison. A promising PPO endpoint must improve lateral RMSE by at least 1%
over LQR, same-supervisor student and both fixed corrections, preserve survival,
improve over the student for every seed, limit nominal degradation to 2%, and
keep heading/actuator-rate RMS within 5% of LQR. All conditions are required.

Original 10 ms deadlines remain unchanged. Offline tracking, asynchronous software
execution and physical sensing-to-actuation latency are separate measurements.
No hard-real-time, global convergence or real-vehicle safety theorem follows
from clipping the residual or observing simulation survival.

