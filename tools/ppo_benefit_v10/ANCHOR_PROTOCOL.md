# Training-only amendment: teacher-anchored PPO

Declared while the original 864-episode comparison is running, before its
assessment exists or any prospective performance outcomes have been inspected.
The sole trigger is training-only diagnostics: all three on-policy endpoints
have worse weighted teacher fit than their fixed BC endpoints (approximately
0.00515..0.00655 versus 0.00448..0.00453). This motivates testing retention of
the useful initialization during PPO updates. Original endpoints, budgets,
outcomes and assessments remain unchanged. No new seed/checkpoint selection.

Start each seed 42/43/44 again from its exact saved BC endpoint, not a selected
PPO checkpoint. Run exactly 16384 further on-policy steps per seed (49152 in this
separate arm). The same environment, reward, observations, guards and expiry
remain. At every PPO optimizer step, add the gradient of 0.5 times weighted
teacher action-mean squared error on a fixed-RNG 128-example training minibatch,
then clip the combined gradient norm to 0.5 before the Adam update. PPO's own
initial gradient clip is retained. This is PPO with supervised regularization,
not a claim that pure PPO or an entirely new method produced every improvement.
Use optimizer pre-hooks and test that the hook executes with actual PPO updates.

After all three endpoints freeze, execute 216 additional episodes: all three
actors on the exact same frozen 72 prospective cases. Original reference
outcomes remain unopened until this arm's source is frozen. Case reuse is a
declared prospective comparison; neither case outcomes nor the original
assessment may drive training choices. Match the frozen policy/source hashes.
Retain every episode and all failures. Compare anchored PPO with adaptive-only,
old v8 PPO, BC-only, direct teacher and unregularized PPO using the existing 36
strata/5000-draw bootstrap and unchanged safety/progress/quality gates. Report
supervised-regularization effects separately from original PPO fine-tuning.

The total successful new PPO budget for both arms is 98304 steps. Earlier
interrupted rollouts remain additional evidence, never silently erased.
