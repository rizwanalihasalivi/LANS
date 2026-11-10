# Continued-supervision control, declared before anchored outcomes

An anchored PPO improvement over the initial BC endpoint can come from extra
teacher updates. Add a continued-BC control before any anchored prospective
outcomes exist. For every seed, start from the same exact BC endpoint and use
1280 teacher minibatches, matching the anchored arm's optimizer-step count:
batch 128, RNG 9000+seed, coefficient 0.5, Adam learning rate 1e-4 and gradient
norm 0.5. Use the same teacher dataset. No PPO policy/value loss, rollout or
environment reward is used in this control. Its additional supervised steps
must never be counted as new PPO steps. Keep all three endpoints.

Evaluate each once on the same 72 registered prospective fixtures: 216 more
episodes, bringing total evaluation to 1296. Compare teacher-anchored PPO with
continued BC using the same paired 36-stratum bootstrap. Positive confidence
against initial BC alone does not establish an incremental PPO benefit when
continued BC performs equally well or better. No policy selection or tuning may
follow these outcomes. Original budgets and raw records remain unchanged.
