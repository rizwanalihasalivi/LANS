# LANS Opening Report: Research Update

**Rizwan Ali — Supervisor: Jie Tian**  
**Research update: 27 October 2026.** This accompanies the earlier opening report;
it does not retroactively validate historical numbers or constitute final
institutional submission. Student number and official major remain to be supplied.

## Research problem and scope

The thesis investigates whether bounded learned steering assistance can improve a
strong analytical path tracker when learned commands are delayed or unavailable.
The agreed architecture is independent LQR baseline plus asynchronous PPO residual
and a predictive rule-based supervisor. PPO full-command control with LQR-only
switching is a different architecture and is outside this campaign.

## Architecture and actual state convention

The executed control law is

\[
\delta_{\mathrm{cmd},t}=\operatorname{sat}_{[-0.5,0.5]}
\left(\delta_{\mathrm{LQR},t}+w_t\Delta\delta_{\mathrm{sel},t}\right).
\]

The evaluated internal error state is $[e_y,v_y,e_\varphi,r]^\top$.
The paper's rate-state representation requires the small-angle transformations
$\dot e_y\approx v_y+v_xe_\varphi$ and
$\dot e_\varphi\approx r-v_x\kappa$; these states must not simply be renamed.
The simulator assumes available map station/reference preview and noisy lateral,
heading, yaw-rate and speed sensing; this is not a complete localization system.

Observation Builder uses estimated state, measured speed, reference curvatures,
actual steering and observable execution history. Twenty channels are retained
for exact actor transfer, with five unavailable pending/forecast/service channels
fixed to zero. Available packets are delivered before building observations.

The local LQR uses the frozen speed schedule/feedforward. A separate PPO worker
proposes a residual in $\{-0.08,-0.04,0,0.04,0.08\}$rad. The supervisor rejects
invalid/stale packets, checks a nominal predicted cost improvement, and manages
bounded residual authority. A50ms proposal-age cutoff is distinct from the
manuscript's5ms gain threshold and from actual CPU inference duration. Three
favourable CONTROL TICKS define admission persistence, potentially using a held
packet; these are not three independent fresh responses. Authority increases at
most0.05 per tick; rejection revokes authority immediately.

Final steering angle and actuator rate are limited; a0.05s actuator lag is modeled.
Predicted cost improvement and LQR fallback do not constitute a nonlinear safety
certificate. LQR's actual execution timing must be measured, not assumed.

## Objectives

1. Establish consistent state, steering, sensing, actuator and packet semantics.
2. Train causal bounded PPO residuals and distinguish their incremental value
   from supervised initialization and simple nonlearned corrections.
3. Evaluate predictive/freshness supervision and recovery against simple gains.
4. Separate inference duration, packet age, queue/IPC and local deadlines.
5. Measure heading/steering tradeoffs, survival and mirrored-path behavior.
6. Confirm only a frozen eligible design on reserved data; keep failures visible.
7. Assess native integration separately from actual target-hardware readiness.

## Proposed contributions and prior work

Residual learning, predictive filtering, delayed-observation shields and backup
runtime-assurance architectures already exist. This thesis targets explicit
causal execution semantics, predictive residual authority and matched attribution
under vehicle tracking conditions. Novelty and the neuro-symbolic label remain
subject to a broader verified review and demonstrable mechanism benefit.

Primary supplied texts include Wabersich–Zeilinger predictive safety filtering;
Tearle et al. learning-based racing filtering; Cano Cordoba et al. delayed
observation shielding; Kalaria et al. delay-aware robust driving/racing; and
Tabrizian et al. delay-aware merging. Their safety proofs, tasks and delay types
must not be replaced by a direct ranking of unlike percentages.

## Frozen new campaign

Six causal PPO pilots use three seeds, scratch versus supervised initialization,
and25,000 additional steps each:150,000 total. Pretraining is extra budget. The
reward uses executed lateral/heading error, steering effort/movement and failure;
no exogenous delay penalty is claimed to train faster CPU execution.

The864-episode development grid includes15/25m/s, sine/DLC, exact left/right
mirrors, nominal/tire-mismatch/20ms/100ms service conditions and nine methods.
All episodes record true heading error, lateral error, actuator movement,
residual authority and measured processing. Mirrors share canonical noise and
signed initial conditions; they are not independent training seeds.

The latency-gain comparator is a disclosed manuscript-inspired reconstruction,
with a common stale cutoff and authority cap, not an exact published-method
reproduction. Confirmation uses new noise and held-out sine parameters only if
predeclared criteria pass. Native Webots and actual-worker tests are separate.

## Claim corrections

The original49x speedup, GPU energy ratio, p99-as-WCET, broad generalization,
>200ms delay bound and global stability claims are not inherited. Finite envelope
survival is not Lyapunov stability. Bounded residuals support only a conditional
nominal disturbance-bound argument, not automatic zero-error convergence.

Physical sensor-to-command and actuator validation require hardware. The laptop
kit measures exported actor/IPC timing only. General-purpose cloud execution
cannot establish guaranteed100Hz or vehicle readiness from finite tests.

## Evidence and remaining work

The campaign's status.json and generated result tables are authoritative for
completed/failed stages. Matching a published controller, final bibliography
metadata, physical testing and any formal nonlinear safety guarantee remain
explicit external/theoretical gaps. The generated manuscript is a research draft.
