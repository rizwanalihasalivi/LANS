# Recover the 7.685% PPO experiment

User request: recover the historically highest aggregate PPO configuration, investigate its +83.30% steering-rate RMS and student gap, correct the causes where supported, and retest. Original evidence is `reviewer-followup-v2/age_original/ppo`; all three corresponding v1 PPO seeds and paired students must be retained. No cherry-picked single seed or scenario.

Starting branch: `reports/opening-report-2026-10-26`; parent commit: `e3a52f49930fcc3dc1ce7426dde6ea5edeec1cc8`.

## Progress

- [x] Identify original three checkpoints, controller, plant, noise grid and raw traces.
- [x] Inspect original training/deployment mismatch and command-change versus actuator-rate reward.
- [ ] Reproduce original PPO/student/LQR episodes and independently quantify chatter, saturation, residual changes and same-input actor drift.
- [ ] Implement and independently test causal smoothing and an actuator-rate budget, preserving immediate stale/LQR fallback.
- [ ] Freeze fresh matched development, a finite matched-training ablation and all acceptance criteria before seeing outcomes.
- [ ] Run, independently replay, report and publish every result. No reserved tests or vehicle readiness claim.

No new result or successful fix is claimed yet. Original frozen files remain unchanged. New work is isolated under `tools/reviewer_v13`.

Training will use the full-state atomic checkpoint mechanism verified in v12, with checked model/optimizer/environment/queue/RNG restoration. Completed evaluation episodes will be saved individually. Updates and resume instructions will be committed/pushed at milestones.
