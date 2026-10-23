# Discussion and decision record

Recorded 24 October 2026 (Asia/Shanghai). This is a structured summary, not a verbatim transcript.

## Progression

1. Set up the LANS cloud Python environment and verify existing code with small smoke checks.
2. Explore CARLA: Python client available, server unavailable in this environment; no supported GPU/server setup established.
3. Install SUMO and verify TraCI. Discuss highway-env as a lightweight RL environment and SUMO as a traffic simulator; neither substitutes for detailed CARLA-like vehicle validation.
4. Install Webots R2025a with CPU rendering and verify physics/camera operation. Select dynamic bicycle as primary research plant and Webots as secondary validation.
5. Review the supplementary package and submission candidate without executing their supplied reproduction code or editing the paper.
6. Integrate ARIS at the user's request; do not initiate ARIS reviews, autonomous research or overnight loops merely because it is installed.
7. Discuss adding a symbolic supervisor to the original residual LQR–PPO architecture. Initially propose latency-aware residual gating and an optional later predictive rule.
8. User specifies that PPO should contribute more in normal operation, LQR should take over excessive delay/error, and PPO should regain influence after recovery.
9. Select full-command PPO-dominant weighted fusion. Earlier residual equations are historical alternatives, not the selected updated design. Preserve residual LANS as a comparison baseline.
10. Select asynchronous PPO and independent fixed-rate local LQR, with freshness monitoring, fallback and controlled recovery.
11. Retain manuscript vehicle parameters; distinguish manuscript-defined values from verified Tesla specifications. Propose nonlinear tire evaluation, actuator dynamics, sensor noise, feasible reference paths and matched experimental comparisons.
12. Review specification v0.1. Parameter values and citations remain candidates; no stability, safety, novelty or performance claims are established for the proposed architecture.
13. User requests publishing completed work and all discussion to GitHub before beginning experiments. This checkpoint implements that request; experiments are not launched by the publication step.

## Decisions still needed during development

- Observation/state estimator, controller input fairness, sign conventions and reference representation.
- Validated state envelope, LQR operating domain and behavior when neither controller is valid.
- Asynchronous worker/queue policy and simulated versus measured timing protocol.
- Full-command magnitude rule, nominal PPO weight, age weighting curve, rejection/recovery thresholds and recovery ramp.
- Path geometry and feasibility, primary-source references for any ISO-derived claims.
- Final training curriculum, convergence criteria, seed allocation, evaluation metrics and failure criteria.

Use the staged freeze in [specification-v0.1.md](specification-v0.1.md). These are unresolved implementation/research choices, not evidence that the proposed design has been tested.
