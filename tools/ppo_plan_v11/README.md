# Isolated sequence-PPO study

This directory extends PPO's action from one steering residual to eight residual
knots over a two-second horizon. The 40 input features contain received state,
estimated dynamics, issued-command history, previous knots and original proposal
ages. They contain no future plant or traffic truth. The owner evaluates a fresh
plan against the unchanged v8 analytical decision, using the original physical,
freshness, collision, corridor and predicted heading/rate limits.

This is an isolated research branch based on v10 commit
`5eb8ff4cfd808c80090e8ac95649bf53ce3ebbb6`. It changes only
`tools/ppo_plan_v11/`. It does not repair or promote the shared v8 controller.

## Experimental meaning

The target is a ten-percent reduction in whole-episode RMSE against the strong
adaptive/MPC reference. The study also reports total hybrid gain against LQR and
incremental gain against initial behavior cloning. These are different claims.
A successful numerical audit means that the recorded evidence replays; it does
not mean the ten-percent performance and quality gates passed.

`PROTOCOL.md` declares 192 training-only probe episodes. The computed sequence
teacher is causal but is an analytical search, not PPO. Its training-only gain
is 0.509052% against adaptive/MPC. The diagnostic does not establish a global
performance ceiling or the benefit of reinforcement learning.

`LEARNING_PROTOCOL.md` declares a 7680-example causal teacher dataset, three
independent BC initializations and 32768 genuine PPO transitions per seed. The
original sequence run completed 98304 on-policy transitions. Saved Adam states
show only 33/33/32 optimizer steps, although the old manifest field named
`actual_ppo_updates` contains SB3's epoch counter of 32. This distinction is
reported explicitly in the independent audit.

`DAMPED_PROTOCOL.md` was registered from those training diagnostics before the
original prospective assessment existed. It declares another 32768 PPO
transitions per seed, starting from each exact initial BC checkpoint. Actor
parameter changes are damped by 0.01 after ordinary Adam updates; critic steps,
reward, action distribution, data, KL threshold and controller limits remain
unchanged. There are no extra imitation gradients in this correction.

The prospective cohort has 72 fixtures: four traffic scenarios, speeds 8/12/16,
delays 0/50/100 ms and two mirrored variants. Original LQR, adaptive/MPC, direct
teacher, scalar PPO, sequence BC and sequence PPO require 864 episodes. The
registered corrected sequence arm adds 216 episodes on the same cohort. This is
72 fixtures with repeated policies, not 1080 independent road scenarios. Paired
confidence intervals resample 36 scenario/speed/delay groups, retaining mirrors
and all three seeds together. No seed or checkpoint is selected from outcomes.

The 100 ms delay combines with the 50 ms service to exhaust the strict 150 ms
freshness budget. PPO consequently has no authority on those fixtures. They
remain in all whole-run averages. Removing them would change the research claim.

## Recovery and checks

Use Python 3.10 and the recorded execution manifest. Numerical replay uses the
repository's original v8/v9 mathematical dependencies and v10 scalar policies;
restore their evidence at the cloned repository root first. In particular the
original legacy model is in
`tools/unified_campaign/evidence/python-v2-training.zip`, and v10's complete
policies are recoverable with `tools.ppo_benefit_v10.package`.

```bash
python -m tools.ppo_plan_v11.package --verify
python -m tools.ppo_plan_v11.package --restore /workspace/sequence-ppo-restored
```

For replay, restore at a clean clone's root rather than the example destination.
Existing evidence files are never overwritten. Then run:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m tools.ppo_plan_v11.verify_learning
python -m pytest tools/ppo_plan_v11 -q
```

The numerical audit reconstructs all teacher queries, checks saved source/model
hashes, replays actual physics and delayed commands, reruns the full analytical
reward shadow for every PPO transition, checks every admitted sequence using an
independent Python three-model rollout, reproduces deterministic neural actions
on prospective cases and independently recomputes paired confidence intervals
and performance gates. It does not rerun complete stochastic Adam trajectories.

For a new study, the one-shot collectors deliberately refuse to overwrite an
existing output directory. The dataset/training stages are `train collect` and
`train train`. Each driver enforces its registered prerequisites. In particular,
`damped` needs the original evaluation protocol to exist while its assessment
is still unavailable; it is registered during that evaluation, not after its
outcome is inspected. `evaluate_damped` needs both sets of frozen endpoints.
Replaying the existing study does not require new training.

`inference.py` provides a versioned 40-input/eight-output spawned worker and a
defensive owner that copies proposals to immutable tuples. It preserves original
timestamps, bounds pending work and rejects malformed policies or replies. The
functional worker checks do not certify runtime deadlines or native Webots
transfer for these new sequence policies.

Evidence archives retain full raw traces, all endpoint and intermediate models,
BC controls, source snapshots, failed-attempt logs and the completed audit.
Large files are split by bytes and reconstructed with SHA-256 verification;
episodes are never sampled to make archives smaller. No thesis drafts, figures
or presentation tables are generated.
