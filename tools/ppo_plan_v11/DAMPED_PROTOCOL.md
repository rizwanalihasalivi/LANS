# Training-only optimizer correction, before prospective results

The first sequence run uses 32768 on-policy transitions per seed but saved Adam
states show only 33/33/32 actual optimizer steps. The small eight-dimensional
standard deviation and full 1e-4 actor step trigger target-KL stopping after
roughly one minibatch per rollout. This is a training-configuration bottleneck,
not proof that 98304 useful gradient updates occurred. The manifest's SB3
`_n_updates` counter counts epochs, not Adam steps.

Before the first prospective assessment exists or its performance is read,
register one corrected arm. Start all seeds 42/43/44 from their exact saved BC
checkpoints and run exactly 32768 on-policy steps each. Observation/action,
reward, teacher data, initial std, target KL .01, critic rate 1e-4, physical
limits, model guards and freshness remain identical. Damp only actor parameter
changes by 0.01 after each ordinary Adam step; this gives an effective actor
step near 1e-6 while retaining ordinary critic steps. The single saved Adam
parameter group remains load-compatible. Its moments use the actual gradients
at the damped policy; there is no extra imitation update or reward change.
Use pre/post optimizer hooks and test actor/critic changes independently.
Log true Adam-step counts, all endpoints/checkpoints and all failures.

After all corrected endpoints freeze, run 216 extra episodes on the same 72
registered prospective fixtures, once per seed/case. This extension is declared
before the original assessment becomes available and is based only on the
training optimizer counters. Compare with every original reference, initial
BC and the uncorrected PPO endpoint. Total new sequence-arm PPO steps become
196608, and total prospective episodes 1080. Keep every original result and
do not select seeds/checkpoints or change the ten-percent criterion.
