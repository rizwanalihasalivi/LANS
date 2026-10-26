# Execution-aligned predictive PPO development study

27 October2026. Frozen single supervisor/reward variant; old evidence unchanged. No post-outcome tuning or reserved evaluation.

| Source | Tracking gain vs LQR | Heading change | Actuator-rate change | Survival |
|---|---:|---:|---:|---:|
| lqr | +0.000% | +0.00% | +0.00% | 96/96 |
| negative | +0.653% | -2.28% | +2.22% | 96/96 |
| positive | +0.653% | -2.28% | +2.22% | 96/96 |
| student | +1.117% | -0.14% | +2.03% | 96/96 |
| oldppo | +1.151% | -0.16% | +2.05% | 96/96 |
| ppo | +1.445% | -0.27% | +2.66% | 96/96 |

Eligible: False. Reasons: lacks1% gain vs student; lacks1% gain vs negative; lacks1% gain vs positive

All methods share the new supervisor, actuator, observer and causal20-channel contract. Student is original supervised initialization, oldppo is the old25k endpoint, ppo is the new prespecified100k endpoint (or explicitly ineligible futility stop). Extra supervised pretraining is disclosed. Training reward measures actual actuator rate. The1s predictor assumes repeated proposals under healthy worker service for performance estimation; no future completion oracle enters the policy, and this is not a safety certificate.

Three training/noise pairs are small-sample development evidence; control ticks are not independent experiments. Physical readiness and hard real-time execution require separate evidence. No failed test is relabeled as a pass.


## Observed timing and scheduling diagnosis

Timing is deliberately run after training/development have finished. It uses the old fixed age_filtered diagnostic and old25k PPO actors, not the new controller. Thus it isolates scheduling choices; a positive outcome cannot certify the new controller. Both profiles use the two highest available CPUs, nice19 workers/stress and original10ms deadlines. The dedicated-spin profile burns one CPU and is not the laptop default.

| Profile | Missed deadlines | Functional/raw replay | Actual nonzero correction ticks |
|---|---:|---|---:|
| absolute_100us | 717/6000 | True | 1951 |
| dedicated_spin | 694/6000 | True | 1870 |

| Study/profile | Misses | Already >=10ms late at release | Wall control >=10ms | Thread CPU control >=10ms |
|---|---:|---:|---:|---:|
| reviewer-followup-v2/sleep | 687 | 672 | 33 | 33 |
| reviewer-followup-v2/absolute | 305 | 296 | 22 | 21 |
| reviewer-aligned-v3/absolute_100us | 717 | 699 | 32 | 31 |
| reviewer-aligned-v3/dedicated_spin | 694 | 669 | 37 | 36 |

Categories overlap. Elapsed control time minus thread CPU time includes descheduling, blocking, IPC and measurement-boundary differences; it is not an exact OS-only attribution. Cgroup quota, host tasks and preemption remain uncontrolled. Any miss fails strict observed timing. Finite zero misses would still not establish WCET, PREEMPT_RT behaviour, physical end-to-end latency or guaranteed100Hz.

## Work completed and outstanding

- Completed: one prespecified execution-aligned controller/reward study, all pilot/futility endpoints, matched same-supervisor controls, independent raw reward/filter/fusion/model replay, and isolated-from-training scheduling experiment. Failed outcomes remain published.
- New learned candidate development eligibility: **False**. See decision.json for every criterion.
- Reserved/unseen tests remain unopened unless eligibility and a separately frozen corresponding-controller timing requirement both pass. Native selected-winner confirmation follows that gate; historical native interface tests are not new-controller validation.
- The existing Python3.10 full-controller kit remains a verified old-controller development diagnostic. No new-controller laptop deployment is claimed. Actual Windows/macOS execution requires the user laptop; physical sensors/communication/actuators require connected hardware.
- The prior nominal Eq5/Algorithm1 safety-filter specialization remains the scoped published comparator. Reproduction of the full robust algorithm/authors code and complete publisher metadata remain unverified; no literature-superiority claim.
- Original reviewer corrections remain: no exogenous latency reward, real queued worker unavailability, fresh LQR distinct from delayed PPO, no49x speedup, no fabricated ablation frequency, no global stability proof, no energy/blind-distance advantage, full disclosure of negative results and limited generalization.
- This is an evidence report, not an accepted-performance or submission-ready declaration. Additional variants require a new frozen study; thresholds are never changed to relabel a failure.

Reproduce/resume: `python tools/reviewer_v3/run3.py --publish`. Protocol, frozen sources/model hashes, training progress, complete raw traces and decision files accompany this report.
