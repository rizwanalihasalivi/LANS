# Broader-exploration PPO, registered after v11 diagnosis

V11's corrected optimizer improves RMSE by 0.167957% against adaptive/MPC and
0.029108% against initial BC on its opened 72-fixture cohort. Neither provides
the requested ten-percent benefit. These cases are now diagnostic. Do not reuse
them as untouched confirmation, select seeds/checkpoints, weaken the strong
reference, change longitudinal control or relax physical/freshness/quality
guards. No ten-percent result is assumed.

Two remaining training limitations motivate one prospectively specified arm:
the v11 random PPO generator spends one third of its transitions on 100 ms
delay states where PPO has no authority; its Gaussian std exp(-5) explores only
about 0.00054 rad of steering residual around the BC mean. Eight-dimensional
exploration is very narrow. The old PPO generator already covers 50 ms delay;
only the initial 64-fixture teacher dataset omits that delay. Do not claim that
all old reinforcement-learning training omitted 50 ms cases.

Use the identical frozen v11 forty-feature/eight-knot environment, analytical
reward shadow, causal shaping, logical service, FIFO, supervisor and robust
admission checks. Start all seeds 42/43/44 from their exact v11 initial BC
checkpoints, never a selected trained endpoint. Change initial Gaussian log std
to -2.5 (approximately 0.00657 rad residual std). Damp each ordinary Adam actor
step by 0.1, retain critic rate 1e-4, KL threshold .01, 1024-step rollouts,
128-minibatch size, ten epochs, gamma .99 and GAE .95. There are no additional
teacher/BC gradients during PPO training.

Train exactly 65536 on-policy transitions per seed (196608 total). Keep all
three endpoints and every 16384-step checkpoint. Log actual Adam steps, KL/epoch
counters, all physical transitions, stochastic actions, original timestamps,
both reward components and the full analytical shadow. No early promotion.

The causal training curriculum draws uniformly among the four original traffic
scenarios, speeds 8/12/16, delays 0/50 ms and mirrors -1/+1. Draw stiffness
uniformly .75..1.25, lateral magnitude .15..45 m, heading -.02...02 rad, road
phase 10..28, amplitude .9..1.3, NPC shift -5..5 and speed scale .75..1.25.
Use the seeded Gymnasium RNG and nominal packets. These are training states,
not test results. Evaluation retains all 0/50/100 ms delays.

After every endpoint freezes, open a new 72-fixture factorial cohort generated
with namespace 2134123 over four scenarios, three speeds, three delays and two
mirrors, with the same declared parameter ranges. Evaluate LQR and adaptive/MPC
once each, and v10 scalar PPO, initial sequence BC, corrected v11 sequence PPO
and v12 exploration PPO for each of the three seeds: exactly 1008 six-second
episodes. Run all endpoints; no model or case selection. The v11 prospective
results are never pooled with this new cohort.

Whole-run RMSE is the mean of complete penalized per-episode RMSEs. Bootstrap
5000 paired draws over 36 scenario/speed/delay strata using namespace 2134124,
retaining mirrors and all seeds together. The target remains >=10% mean gain
against adaptive/MPC, positive lower 95% limits against adaptive/MPC, initial
BC, scalar PPO and corrected v11, zero collision/corridor failures per actor,
every case's progress >=99% of LQR, and each actor's mean heading/rate <=110%
of LQR. Report whether the adaptive CI lower bound reaches ten percent
separately. A failure remains a failure; every case, metric and seed is retained.

Independently replay dataset/model/source hashes, all training physics and full
analytical shadows, causal observations and reward arithmetic, all admitted
three-model plans, deterministic evaluation actions, reference commands, FIFO,
strict expiry identity and paired statistics. Seal all traces, checkpoints,
protocols and failed attempts in bounded byte-preserving archives. This study
does not certify native Webots transfer, runtime deadlines, publication novelty
or a universal performance ceiling. No thesis draft, figures or tables.
