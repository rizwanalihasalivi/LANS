# Proposed specification v0.1

Status: discussion baseline, not a validated or frozen experimental specification.

## Architecture

PPO and LQR produce independent **complete front road-wheel steering commands**, in radians. This replaces the original residual-PPO architecture; full-command PPO needs new training.

`delta_cmd = sat(w_eff * delta_PPO + (1 - w_eff) * delta_LQR)`

`w_eff = g_s * w_PPO(age)`, with weights in [0,1]. Normal conditions should give PPO weight greater than 0.5; the exact value is a development parameter. Moderate age reduces its weight. Rejected, missing or invalid PPO output selects LQR explicitly (never rely on multiplying NaN by zero).

LQR executes locally at 100 Hz, independently of asynchronous PPO. The supervisor receives vehicle state, PPO output and timing metadata; it passes the full command and gate to fusion. A direct PPO-to-fusion bypass is unnecessary if this pass-through is explicit. Fusion drives the actuator and nonlinear plant, which feeds tracking errors back to both controllers.

Information age is `t_control - t_observation`; inference duration is `t_output - t_inference_start`. Record both; command age is the primary freshness quantity. Avoid double-counting delays. Candidate freshness thresholds are 10/20/50 ms, not selected deadlines. Define worker concurrency, queue/drop policy, timestamps and handling of out-of-order outputs before implementation. Delays change command availability without blocking local control.

Supervisor rules, with rejection taking precedence:
1. Reject stale, missing, nonfinite or otherwise invalid PPO outputs.
2. Reject outputs outside the validated state envelope. LQR fallback is not a safety guarantee outside its own validated domain.
3. Bound excessive full-command output. The previous residual-scaling rule must be reformulated: clipping an action and lowering its fusion weight have different effects. Exact policy remains open.
4. Accept valid, fresh commands in the envelope.

Recovery should use a tighter return threshold and a defined normal-condition persistence requirement, followed by gradual weight restoration. Exact hysteresis, persistence and ramp values remain development parameters. Weighted fusion and switching do not themselves establish stability.

A model-based predictive rule is a later separate extension/ablation. It requires model and LQR inputs and should assess the actual candidate fused command against LQR, not only raw PPO output.

## Vehicle and actuator

Manuscript-defined baseline, not independently verified Tesla Model 3 data:

| Parameter | Value |
|---|---|
| Mass | 1650 kg |
| Yaw inertia | 4224 kg m² |
| Front/rear small-slip cornering stiffness | 80,000 N/rad each, per axle |
| CG to front/rear axle | 1.2 / 1.4 m |
| Nominal speed | 25 m/s |
| Additional evaluation speeds | 15 and 20 m/s |

Linear dynamic bicycle for LQR synthesis; nonlinear dynamic bicycle with Fiala tires for primary evaluation. Document tire conventions and static axle loads; load transfer is omitted initially. Webots is secondary validation, not yet connected to the LANS controller. Predefine speed-based LQR gain computation with common Q/R across methods; fixed-25-m/s gains can be an ablation.

The following are **simulation assumptions**, not established vehicle specifications:

| Parameter | Initial candidate | Sensitivity candidates |
|---|---|---|
| Road-wheel angle limit | ±0.50 rad | ±0.35, ±0.50, ±0.60 rad |
| Steering rate limit | 0.35 rad/s | 0.20, 0.35, 0.50 rad/s |
| Actuator time constant | 0.05 s | 0.02, 0.05, 0.10 s |
| Control period | 10 ms | fixed nominal |
| Plant integration step | 1 ms | verify numerical convergence |
| Tire-road friction | 0.9 | 0.6, 0.8, 1.0 |

`d(delta_a)/dt = clip((delta_cmd - delta_a)/tau_a, -rate_max, rate_max)` with actual angle bounded too. Apply identical actuator physics to all methods.

## Sensing and paths

Proposed independent zero-mean Gaussian noise standard deviations: lateral position 0.03 m, heading 0.17 degrees (convert to radians), yaw rate 0.01 rad/s, speed 0.1 m/s. Sampling 100 Hz; primary sensor delay 0 ms, stress case 10 ms; doubled-noise sensitivity. Define measurement/estimation of all required states and derivatives before freezing. Do not silently expose true states to noisy controllers or directly differentiate white noise without a specified estimator. Use true states for evaluation metrics.

Proposed modified double-lane-change geometry: section lengths 15/30/25/25/15/15 m (125 m total), lateral offset 3.5 m. Vehicle width, corridor boundaries and centerline smoothing still require specification. ISO edition/compliance/dimension claims in the supplied notes are unverified. Until primary sources are checked, call this a modified course, not ISO-compliant.

Screen curvature using `v²|kappa| <= 0.8 mu g` as an engineering preliminary criterion, then check nonlinear tracking and actuator feasibility. The 0.8 margin is not an ISO requirement. Neither 25 nor 22.2 m/s is automatically feasible. The reviewed legacy course demanded approximately 1.76 g at 25 m/s; separate infeasible stress cases from nominal performance evaluation. Do not silently alter standardized geometry.

## Training and comparisons

Initial budget: 1 million environment steps per seed, five seeds, matched budgets for learned methods. Proposed curriculum: 200k at 15 m/s without delay; 400k at 25 without delay on feasible paths; 200k at 25 with delay probability 10% and uniform 5–130 ms; 200k mixed 15/20/25 with disturbances. The delay distribution is attributed to the manuscript in the notes and still needs exact source confirmation. This curriculum is not final and 1M steps does not establish convergence. If increased, change comparable budgets consistently and document why.

Training at all three speeds makes those speed tests multi-speed evaluation, not unseen-speed generalization. Hold out paths, disturbance/delay traces and test seeds. Define how asynchronous observations/actions/log-probabilities/rewards are associated; reward from a held or fallback action must not be incorrectly assigned to a new PPO action. Separate deployment-aware training from standalone PPO training and frozen-policy ablations from retrained variants.

Compare at minimum:
1. LQR.
2. Standalone full-command PPO.
3. Original residual LANS, trained for its original action role.
4. Proposed PPO-dominant weighted fusion.
5. Proposed fusion without symbolic supervision.
6. Fixed-weight fusion.

All share physical scenarios, actuator limits, comparable information and matched random seeds. No-supervisor ablations retain basic numerical validity checks and physical constraints; document exactly which logical rules are removed. Record tracking errors, failures/survival, steering/rate constraints, command-age and inference-time distributions, deadline misses, fallback occupancy and recovery behavior. Aggregate across seeds; do not treat correlated time steps as independent trials. Exact failure definitions, metrics and statistical plan must be frozen before held-out testing.

## Staged freeze

First check plant/path feasibility. Then freeze physical assumptions and training protocol. Select gates, thresholds and recovery behavior on development data. Freeze controller settings before untouched final tests. Run Webots transfer validation afterward with documented vehicle parameters, control interface and scenarios. No new research results exist at this checkpoint.
