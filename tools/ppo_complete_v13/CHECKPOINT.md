# V13 technical continuation checkpoint

This is development work on `research/ppo-complete-v13`, based on v12
`b4aa1898`. Historical code/data remain unchanged. The user authorizes all five
remaining goals, including the shared collision repair and actual runtime/native
validation. No thesis drafts, figures or presentation tables are produced.

Verified so far:

- Shared causal brake-or-clear supervision passes all **288 opened regressions**
  (the 72 v11 and 72 v12 fixtures, each with matched LQR and adaptive/MPC).
  Collisions/corridor failures are zero. All 34560 physical ticks and 82 clearance
  certificates are independently replayed. 285 unchanged ordinary episodes are
  identical to historical records. Repaired case53 briefly reaches17.25m/s
  versus a16m/s tracking target, within the original acceleration envelope.
- All **43 focused integration tests pass**. These include original bounds,
  strict actual proposal ages/deadlines, no extra same-tick slew ownership,
  current-tick action effect at0/50/100ms, true finite task termination,
  exact primary RMSE reward, causal observations, and independent actor/critic
  optimizer state and KL-stop behavior.
- Physical Webots environment readiness passed2000 native1ms steps/2s with
  measured car displacement5.511m. This had no learned policy or collision
  assessment and is **not final native validation**.

The aborted safety v1/v2 logging/auditor attempts are retained. V1 failed ndarray
JSON serialization; v2 generated all288 simulations and then its first audit
encountered NumPy-bool subtraction. The corrected verifier replayed the existing
v2 records without changing controller outputs. Logs are under
`/workspace/cloud-setup/ppo-complete-v13*`; raw verified data are under
`results/ppo-complete-v13/safety-development-v2`.

Current learner: `IndependentPPO`, separate actor/value Adam optimizers and
gradient clipping; actor KL stopping leaves critic epochs running. The unused
stock optimizer remains state0. Encoder55/action8 contract is
`v13-current-anchor55-correction8-finite120-v1`. New policies must be trained;
legacy40-feature weights are not reinterpreted. Scalar RMSE reward is exact for
the fixed120-step task with gamma1 and missing failure ticks penalized6.25m².
Additional terminal heading/rate/progress/failure penalties are logged separately;
the total reward is not claimed to equal pure RMSE. Actor features exclude
privileged plant/shadow truth.

Next steps in order:

1. Finish causal teacher/headroom development on opened cases before expensive
   three-seed learning. Extra anchor quality1.0 versus original-only local1.1
   quality are development alternatives. Preserve all original safety bounds.
2. Freeze a prospective training/control/BC/continued-BC protocol and fresh
   evaluation namespaces before their outcomes. Test real10% gain rather than
   promising it or attributing shared safety/projection to PPO.
3. Complete actual runtime profiling (no concurrent training), physically native
   moving-NPC adapter, common actuator calibration, and final same-policy Webots
   transfer after Python qualification. The readiness smoke does not substitute.
4. Independently replay every new result, retain failed attempts, seal all raw
   evidence and push the isolated branch. No final-pass flag before all gates.

Canonical CLI uses `NUMBA_CACHE_DIR=/workspace/lans-setup/numba-ppo-complete-v13-cli`;
pytest uses the separate `...-tests` cache. Mixing caches caused a retained
module-alias unpickle error (`ppo_complete_v13` versus `tools.ppo_complete_v13`),
which is operational rather than a controller failure.
