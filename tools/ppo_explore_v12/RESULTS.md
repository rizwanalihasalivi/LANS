# Wider-exploration PPO: complete-cohort result and remaining blocker

The requested **ten-percent incremental whole-run RMSE gain was not achieved**.
The new PPO endpoint has the lowest mean RMSE among this cohort's tested
controllers, but the additional benefit is small and the candidate fails
promotion. Its gain against adaptive/MPC is 0.280751%; the extra gain against
initial imitation is 0.094173% with a confidence interval crossing zero.
A shared 100 ms crossing collision and one actor's heading threshold also
disqualify the candidate. None of these failures is removed from the record.

## What was actually completed

All seeds 42/43/44 started from their exact v11 initial imitation checkpoints.
Saved initial-model comparisons confirm identical mean-policy and critic
weights, zero optimizer steps, and only log standard deviation changed to -2.5.
Training used wider stochastic exploration, actor-step damping 0.1 and a
curriculum concentrated on controllable 0/50 ms delays. Physical dynamics,
40-feature/eight-knot inference, all reward mathematics, longitudinal
supervision, the 150 ms freshness rule and three-model admission guards are
the frozen v11 implementation. There were no additional imitation gradients
during PPO training.

Each seed completed **65536 actual on-policy transitions and 5120 Adam steps**
(640 SB3 epochs). This study adds **196608 genuine PPO transitions**. Every
initial model, 16384-step checkpoint and final endpoint is retained. No seed
or checkpoint was selected from outcomes.

The prospective comparison completed **1008 episodes** on a new 72-fixture
factorial cohort, with four traffic scenarios, three speeds, three actuator
delays and two mirrored variants. LQR and adaptive/MPC were tested once per
fixture; scalar PPO, initial sequence BC, corrected v11 and v12 were each tested
for all three seeds. Repeated policies are not independent road scenarios.

V11's earlier 1080 episodes remain a separate, opened diagnostic cohort.
Together the two sequence studies ran 393216 new PPO transitions and 2088
comparison episodes across two distinct 72-fixture cohorts. Their results are
not pooled to claim one larger independent experiment or a larger gain.

## Full-run comparisons

The new hybrid's mean penalized episode RMSE is **0.105489356 m**. All
comparisons below use the same complete prospective cohort and all seeds.
Positive gain means lower RMSE. Paired 95% confidence intervals use 5000 draws
over 36 scenario/speed/delay strata, retaining mirror variants and every actor.

- LQR, 0.109102723 m: **3.311894% lower**, CI **1.959955% to 4.971861%**.
- Adaptive/MPC, 0.105786352 m: **0.280751% lower**, CI **0.112473% to 0.549527%**.
- Initial sequence BC, 0.105588792 m: **0.094173% lower**, CI **-0.060141% to 0.291711%**.
- Existing scalar PPO, 0.105635472 m: **0.138321% lower**, CI **-0.017052% to 0.344243%**.
- Corrected v11, 0.105569936 m: **0.076329% lower**, CI **-0.093163% to 0.273486%**.

The adaptive comparison supports a small positive mean effect on this nominal
cohort. The BC, scalar and corrected-v11 comparisons do not establish reliable
additional benefit. PPO's extra improvement over initial BC is approximately
**0.000099436 m (0.099 mm)**. The total gain against LQR includes the analytical
controller and BC contributions; it is not entirely reinforcement learning.
The previous cohort's percentages must not be compared directly with these
numbers to claim a causal improvement; the paired v11 comparison above is the
relevant test.

## Shared collision and quality gates

There is **one failed unique fixture**, case **53**, a crossing scenario with
**100 ms actuator delay**. Collision occurs at **2.30 s**. Every tested controller
fails this fixture: LQR and adaptive once each, and the four learned roles for
all three seeds, giving **14 repeated collision episodes**. The v12 candidate
therefore has **3 collisions / 216 evaluation episodes**, all on that same
fixture. There are zero recorded corridor failures on this cohort.

`counterexample.py` independently checks all 14 raw hashes. Every non-LQR
controller's issued commands, applied commands and physical trajectory on this
fixture exactly match the adaptive reference, within 1e-12. No learned proposal
is selected. The 50 ms service plus 100 ms actuator delay exhaust the strict
150 ms age budget, so changing PPO weights cannot change this collision under
the frozen proposal contract. This is a concrete shared-supervision/fallback
repair dependency. Proposal timestamps and freshness limits are not rewritten
to manufacture authority or hide the failure.

The diagnostic is preserved in restored
`results/ppo-explore-v12/diagnostics/shared-collision-case-53.json`, including
the case, all raw hashes, collision time and the checked command/trajectory
identity. This case is now opened regression evidence. A repaired shared owner
needs new matched validation before a final claim; reusing the counterexample
alone would not provide untouched confirmation.

Early collision episodes have 47 observed ticks. Their unrun 73 ticks receive
the unchanged squared-error penalty of 6.25 m² per tick before the 120-tick RMSE
is computed. Failed cases, 100 ms cases and all seeds remain in every average.

Mean heading RMS is **9.377614% higher than LQR**, and steering-rate RMS is
**4.308925% higher**. Actor 43 individually exceeds the declared 110% heading
threshold. The per-case progress requirement against LQR passes on this cohort;
the minimum ratio is **99.380642%**. These outcomes do not support superiority
in every metric. The new PPO proposal is selected on 330 recorded ticks versus
1682 for corrected v11; larger training effort does not guarantee more authority
or a larger whole-run benefit.

## Verification, recovery and claim limits

The registered protocol and all source preceded new training and fresh-case
evaluation on branch `research/ppo-explore-v12`. `README.md` explains recovery
and full numerical replay. All raw data, failed attempts, model endpoints,
checkpoints, initial controls and source snapshots are retained in bounded,
byte-preserving evidence archives after verification finishes. A successful
numerical audit certifies the consistency of recorded experiments, not the
failed performance and safety promotion criteria.

These remain nominal-network simulations on a bounded four-scenario domain.
Native Webots transfer, actual deadline certification, untouched final
confirmation and a substantial PPO-versus-BC benefit are not established for
this candidate. It is not promoted into the shared controller, and no
ten-percent, universal-safety or publication-ready superiority claim is made.
