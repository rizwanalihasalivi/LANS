# Registered eight-knot PPO learning experiment

The training-only computed teacher improves RMSE 0.509% versus adaptive-only,
but its 110.612% heading ratio fails the original <=110% actual gate. It is
therefore a diagnostic initialization, not a promoted solution or a demonstrated
10% result. PPO may optimize actual episode return differently; no 10% outcome
is guaranteed by the teacher or by a larger training budget.

Reconstruct causal query observations from every saved sequence-teacher training
transition, using only current received state, previous received NPC state,
estimated model and issued/applied history. No next-step truth is an input.
The new contract has 40 features: the v10 30-feature observation, last eight
submitted knots, and logical/wall ages of the received plan. Actions are eight
normalized knots projected through the original v8 physical/residual limits.

For each seed 42/43/44, initialize a new 128x128 actor/critic with this distinct
40-input/8-output contract. Train 32 BC epochs on the full teacher dataset and
retain the BC-only checkpoint. Then run exactly 32768 actual on-policy PPO steps
per seed, retaining all three endpoints and checkpoints. Optimizer is new and
old scalar models are not relabeled. PPO learning rate 1e-4, n_steps 1024,
batch 128, epochs 10, gamma .99, GAE .95, zero entropy coefficient, initial
normalized action log standard deviation -5 and target KL .01 to limit destructive
updates in the narrow admissible plan region. No teacher-gradient hook in this
experiment; the BC-only comparison isolates genuine PPO fine-tuning.

Use the same randomized training distribution as v10 and a separate matched
v8 adaptive/MPC shadow for actual reward. Actual reward is the v10 scaled/clipped
cost difference (8 tracking, 4 heading, .04 steering-rate, .002 acceleration),
minus 20 on collision/corridor failure. Add 0.25 times a causal predicted-plan
relative improvement, clipped to [-1,1], compared with a zero-knot plan; an
inadmissible predicted plan receives -0.25. This model shaping uses only current
received data, estimated dynamics and the known FIFO. It is not future truth or
a replacement evaluation metric. Log both reward parts separately. The actual
first command remains delayed; observations include pending plan information.

After source/models freeze, use 72 new fixtures generated with namespace 2134113
on the v10 factorial design (four scenarios x speeds 8/12/16 x delays 0/.05/.1 x
two mirrors). Every case receives LQR, strong v8 adaptive/MPC, direct sequence
teacher, the three v10 anchored scalar actors, three BC-only sequence actors and
three new PPO sequence actors: 864 episodes. Keep six-second failure-penalized
RMSE, every failure, all actor endpoints, progress and quality metrics. Bootstrap
the 36 scenario/speed/delay strata, 5000 draws with seed 2134114. Compare PPO with
adaptive-only, scalar PPO, BC-only and direct teacher; report all means/intervals.
Primary requested goal is >=10% whole-run gain versus adaptive-only with positive
confidence, positive incremental PPO benefit over BC-only, zero failures, >=99%
every-cell LQR progress and each actor's mean heading/rate <=110% LQR. Also report
LQR-relative gain separately. Do not tune or select checkpoints on these outcomes.
No thesis draft, figure, table, native or actual-runtime claim is authorized here.
