# LANS reviewer-issue investigation: submitted-action credit and timing


27 October 2026. Finite development evidence; no claim that every requested requirement passed.


## Diagnosis and intervention


Scope remains the original residual LANS architecture: LQR baseline plus a bounded categorical PPO correction approved by the predictive freshness/cost supervisor. It is not full-command PPO/LQR switching. A 1,000ms delayed PPO worker with fresh local sensing is not 1,000ms delayed LQR feedback. The actor chooses one of −0.08, −0.04, 0, +0.04, +0.08 radians; measured neural inference, injected post-inference service wait, packet age and local-loop response time are distinct quantities.

The preceding 1,500-tick smoke had 274 original-deadline misses. Of these, 261 were already at least 10 ms late on release. Both wall-processing and thread-CPU spikes were recorded. These measurements identify multiple contributions; they do not establish a unique OS/cgroup cause or excuse any miss. Historical unrecorded throttling cannot be assigned to an individual episode.

Fixed-tick PPO previously sampled actions even when its worker queue was busy. Recorded delay-100ms development cases discarded about 90% of samples; delay-20ms cases discarded about 50%. Such actions do not affect the plant but still contribute actor surrogate, entropy and KL terms. This motivates a variance/credit-assignment ablation, not a claim that the original expected policy gradient was necessarily biased.

A separately frozen two-arm study starts both arms from the same paired v5 no-history endpoint, including critic and optimizer. Each arm receives exactly 100,000 additional transitions for each of three seeds, with fresh training and development noise namespaces. The all-actions arm retains every actor sample; submitted-only masks actor loss, advantage normalization, entropy and KL to actual submitted requests. Fixed-tick GAE, all-transition critic loss, deployed controller, reward, actuator limits and all acceptance margins are unchanged. Environment budgets match; effective actor sample counts differ and are reported below.

$$L_\pi=-\frac{\sum_i m_i\min(r_i A_i,\operatorname{clip}(r_i,1-\epsilon,1+\epsilon)A_i)}{\sum_i m_i},\quad m_i=\mathbf{1}\{\text{request submitted}\}.$$

Actor/entropy/KL means and advantage normalization use valid samples. This also changes actor-loss scaling relative to the unchanged all-transition critic when the valid fraction is below one, so the intervention is not an isolated proof about variance alone. In a minibatch with no valid requests, only the critic is updated. The all-actions control sets every mask to one.

$$r_t=-\left(\frac{e_y}{0.5}\right)^2-0.2\left(\frac{e_\varphi}{0.1}\right)^2-0.2\left(\frac{\dot{\delta}_a}{0.35}\right)^2-0.005\left(\frac{\delta_{\mathrm{cmd}}}{0.5}\right)^2-10\,\mathbf{1}\{\text{failure}\}.$$

The input remains causal_filter_history_v5. Coordinate 14 is known filter history and its actor weights remain exactly zero in both arms; future-completion/output/service coordinates remain zero. This is not another history-feature search. Both arms inherit v3 100k and v5 100k PPO training plus original supervised pretraining. Additional optimization cannot be attributed solely to masking.

Four implementation contracts passed: all-valid update is bitwise identical to reference PPO, no-valid sample preserves actor parameters while updating critic, discarded advantages/log probabilities do not affect the actor update, and different busy-worker actions produce identical physical transitions. The generated surrogate uses checked edits to SB3 2.0.0 training code; no reserved data were used.


## Frozen fresh development comparison


Completed **600,000 additional training transitions** and **672 episodes**. These are known-path development conditions, not unseen-path confirmation.


| Controller | Lateral RMSE m | Gain vs LQR | Heading change | Actuator-rate change | Survival |
|---|---:|---:|---:|---:|---:|
| LQR | 0.090413 | +0.000% | +0.00% | +0.00% | 96/96 |
| Fixed −0.04 | 0.089372 | +1.151% | -3.30% | +3.36% | 96/96 |
| Fixed +0.04 | 0.089372 | +1.151% | -3.30% | +3.36% | 96/96 |
| Same-supervisor student | 0.088549 | +2.061% | -0.31% | +3.14% | 96/96 |
| Frozen v3 PPO | 0.088093 | +2.566% | -0.52% | +4.01% | 96/96 |
| Additional PPO: all actions | 0.088269 | +2.371% | -0.59% | +4.46% | 96/96 |
| Additional PPO: submitted only | 0.088052 | +2.611% | -0.51% | +4.51% | 96/96 |

| Arm / pair | Environment transitions | Submitted actions | Actor credit samples |
|---|---:|---:|---:|
| all_actions / 0 | 100000 | 63191 | 100000 |
| all_actions / 1 | 100000 | 68233 | 100000 |
| all_actions / 2 | 100000 | 63887 | 100000 |
| submitted_only / 0 | 100000 | 63191 | 63191 |
| submitted_only / 1 | 100000 | 68233 | 68233 |
| submitted_only / 2 | 100000 | 63887 | 63887 |

Student-relative tracking gains: all-actions **0.316%**; submitted-only **0.561%**. The original requirement is at least 1%, with the complete balanced/fixed-baseline/per-pair screen also required. Selected arm: **None**.


- all_actions: lacks1% gain vs student; pair2 no student gain. Three paired student gains: 0.708%, 0.358%, -0.116%.
- submitted_only: lacks1% gain vs student. Three paired student gains: 1.183%, 0.142%, 0.363%.

Independent replay verified **922,992 transitions**, **342,864 submitted actor decisions**, every observation coordinate, actual rewards, observer/plant states, gate/filter decisions and commands. All 144 100ms-delay/LQR trajectory pairs matched exactly. No per-seed arm mixing or endpoint extension was used.


The post-hoc per-condition breakdown exposes an aggregate limitation: at15m/s the submitted-only arm increases actuator-rate RMS by roughly10.8–12.4% in active nominal/tire/20ms cases, despite an overall4.51% mean increase. At25m/s nominal it gains about1.485% over the student, while tire uncertainty and delayed cases offer less additional gain. The original screen constrains the aggregate, not every speed/scenario. No uniform balanced-performance claim is made, and the post-hoc table does not change selection thresholds.

This is a fresh development grid and a new trained endpoint study, not an identical rerun of the older0.943% v5 result. The original v5 initializer was not separately reevaluated in this grid, so a cross-campaign difference cannot isolate optimizer drift from noise/model effects. Only the paired all-actions/submitted-only comparison isolates the declared intervention under this design.


## Original 10 ms timing


The separate serialized campaign recorded **657/7500 controller deadline misses**, with functional fallback **True** and observed strict timing **False**. The native C heartbeat recorded **587/3000 misses**. All three actor seeds and five actual worker cases were tested, with full warmup, pinned control/helper CPUs, lower helper priority and no concurrent research jobs. Source/model hashes, original unshifted 10ms targets, all causal gate observations, packet actions, fault injection and software-plant trajectories were independently replayed.

Timing model provenance is in timing/protocol.json. If no new controller qualifies, this remains a platform diagnostic with the unchanged v5 actor, not selected-controller validation. Scheduler behavior remains a platform requirement; lower average inference time does not establish a 100Hz response guarantee. Zero finite misses, if observed, would also not constitute WCET certification.

The local LQR, observer, IPC and supervisor still share one process. Independence from the PPO worker is not independence from local scheduling or computation stalls. Deadline fallback is recorded at a software commit marker, not at an actuator. The fixed-step plant pauses while the host stalls; survival does not establish physical continuous-time safety. No deadline is shifted, skipped or forgiven.


The portable entry point now explicitly sets one BLAS/OpenMP thread before numerical imports. Two subprocess checks with conflicting inherited thread settings verify that policy and also establish that the previous common boot already enforced the BLAS limit indirectly. This is import-order hardening, not evidence that excess BLAS threads caused the previous 274 misses or that a new speedup was achieved.


The new three-actor Python3.10 kit has a separate clean-environment portability smoke: 750 ticks, 5 misses, functional fallback True. This is a short cloud packaging check, not the actual Windows/macOS target result or a full selected-controller qualification. The complete user command runs15 cases of13seconds each, plus warmup/replay, then writes laptop-results/Results.zip. No Torch/GPU is required.


## Robust published-filter contract and bibliography


A separate implementation of the uniform-error specialization of Wabersich/Zeilinger arXiv:1812.05506v4 Eq.(6), Eq.(9–10), Algorithm 2 was completed for an explicitly declared scalar bounded-error/full-state plant. All **3000 transitions** satisfy declared state/input bounds, and **2760 inputs** match independently solved LP optimal-input intervals. Full-horizon, shrinking-horizon and terminal branches are exercised; uncertified initial states are rejected.

$$x_{k+1}=0.8x_k+0.2u_k+w_k,\quad |w_k|\le0.01,\quad |x_k|\le1,\quad |u_k|\le0.5.$$

The terminal interval is |x|≤0.2 with u=−x. Incremental V=e² contracts by rho=0.36 under pi=v−e; tightening epsilon=0.06 dominates the declared normalized disturbance bounds. The exact assumptions, solver tolerances and traces are preserved. This is an independent scalar algorithm specialization, not the authors’ code/examples or a matched nonlinear LANS vehicle reproduction. It does not supply a validated vehicle error/confidence set, noisy-state certificate or vehicle terminal safe set.

All **32 original bibliography entries** were structurally reviewed. The five uploaded primary papers support five version-specific references already preserved. Entries 18/26 conflict in venue metadata and need deduplication/correction using the supplied Kalaria version; entries 23/24 duplicate a title with different author attribution. Several ECU/GPU/WCET assertions cite sources that do not directly substantiate those exact claims. Full primary-source verification of every remaining entry is pending; unsupported claims are not retained as established facts.


## Completion boundaries


Combined development-selection and observed-timing gate: **False**. Reserved data remain unopened unless both gates pass and a corresponding confirmation protocol is frozen. No current native Webots or unseen-path result is manufactured. Prior native interface checks are not confirmation of these new policies.

Still required: full scientific selection if failed; target-specific original10ms timing; actual Windows/macOS laptop execution; gated reserved/native confirmation; matched robust vehicle comparator and remaining primary-source citations; connected physical sensor/communication/actuator measurements for vehicle readiness. The available cloud has no connection to the user laptop or a vehicle, so those measurements cannot be honestly marked complete.

The report is an evidence draft, not a submission-ready superiority/safety paper. Claims of global convergence, neuro-symbolic novelty, vehicle readiness, energy advantage, total blind-distance improvement or 49-fold speedup remain unsupported. Repeated development campaigns and cumulative training budget must be disclosed; these finite means are not a population guarantee.

Resume software work with `python tools/controller_review/run_credit_work.py --publish`. Frozen failures remain preserved; the command does not lower thresholds or manufacture hardware results.
