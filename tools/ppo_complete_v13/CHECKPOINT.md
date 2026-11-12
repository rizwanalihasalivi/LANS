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

Additional verified continuation work:

- Full opened72-case causal teacher collection is complete:144 paired episodes,
  no failures,8640 real teacher frames,4773 nonzero correction labels. Mean
  RMSE is0.080278550m versus repaired analytic0.080671173m (0.486694% gain).
  This is computed teacher evidence, not PPO benefit. Mean heading/rate ratios
  to the analytic owner are1.01928/1.01551. These are development cases only.
- The prospective learning/control protocol is frozen in TRAINING_PROTOCOL.md.
  Three seeds42/43/44 are training for65536 genuine PPO transitions each.
  All initial actors, continued-supervised controls and final endpoints are
  retained; no favorable checkpoint selection. Actual Adam counters are pinned
  and supervised optimizer states are separately saved. Initial seed42 BC and
  critic warmup have been reproduced byte-for-byte:2176 supervised and120 value
  optimizer updates,3840 physical/shadow transitions and32 complete episodes.
- Current combined focused suite passed100 tests. Evaluation namespaces remain
  unopened until every declared endpoint and continued-BC control freezes.
- Native acceleration-command mapping now uses real electric-engine torque
  and four mechanical brakes. Policy-free8-condition/8000-sample calibration
  independently verifies settled acceleration RMSE0.088864m/s2; earlier poor
  cruise/torque attempts remain. This is calibrated surrogate fidelity, not
  pointwise exact acceleration or final policy transfer.
- The moving-traffic native adapter now uses policy-free measured warmup
  displacements to initialize world positions. Every car reaches its initial
  scene through native physical motion, with no pose/velocity/force overwrite.
  Opened crossing case53 v4 independently verifies6000 actual1ms physics
  samples/120 control ticks,0 collision/corridor failures and1.43524m minimum
  circle clearance. Initial traffic position error is8.3e-12m and speed error
  -0.0122m/s. Physical measured steering-rate RMS is separately distinguished
  from commanded rate. This concurrent-training development run has0 owner
  deadline misses but84 scheduled misses; it does not qualify formal timing.
  Failed/stale initial-scene attempts v1-v3 and their audits remain intact.

Remaining stages in order:

1. Finish the fixed three-seed learning budget, update-matched continued BC and
   independent training audit. No10% result has been established for v13.
2. Run all864 validation and1728 untouched final episodes, retaining12 matched
   roles/case, original guards, all actors, failures and36-stratum intervals.
3. Complete actual runtime profiling without concurrent learning, then frozen
   same-policy representative native transfer. A failed Python performance gate
   remains failed even if downstream engineering diagnostics complete.
4. Independently replay every new result, retain failed attempts, seal all raw
   evidence and push the isolated branch. No final-pass flag before all gates.

Canonical CLI uses `NUMBA_CACHE_DIR=/workspace/lans-setup/numba-ppo-complete-v13-cli`;
pytest uses the separate `...-tests` cache. Mixing caches caused a retained
module-alias unpickle error (`ppo_complete_v13` versus `tools.ppo_complete_v13`),
which is operational rather than a controller failure.
