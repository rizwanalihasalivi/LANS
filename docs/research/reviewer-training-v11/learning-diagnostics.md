# Descriptive learning diagnostics

All three new runs completed exactly100,000 additional environment steps; optimizer update counts increased from500 to1000, with initial actor/critic/optimizer/reward-normalizer preservation tested. This was an actual continued-training experiment, not reuse of unchanged weights.

On93,960 query vectors visited by the new policy, old/new greedy action agreement is86.9338%; about13.07% of actions changed. Mean categorical entropy on these same inputs changes from0.33772 to0.34626. This same-input calculation separates policy output changes from different visited trajectories; it does not isolate their causal effect on tracking or prove convergence.

Nominal learned authority is nonzero on5.609% of new-PPO ticks versus6.780% for old PPO; mean nominal blending weight is0.007986 versus0.010612. New-PPO activity is2.888% at20ms,0.822% at40ms and zero at100ms. These fractions/weights are not the percentage of vehicle steering supplied by AI, and lower activity does not itself prove the cause of the tracking regression.

The independently checked mean per-episode physical reward-cost decomposition is recorded in learning-diagnostics.json. New PPO's total is0.0695907 versus old PPO's0.0694034. Slightly smoother steering/heading therefore does not establish an improvement in the complete measured reward objective. These development outcomes do not prove every possible PPO or architecture cannot achieve20%; they show this finite continued-training run did not.

The diagnostics are post-hoc descriptions, not new parameter selection, extra training, endpoint cherry-picking or reserved-data evaluation. Their generator/source hash and the verified raw-data seal hash are recorded in the JSON. Last-logged SB3 optimizer metrics are labeled as logs emitted before the corresponding iteration update rather than recomputed final metrics.
