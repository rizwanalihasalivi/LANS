# Controlled exploration and curriculum for sequence PPO

This isolated study follows the small v11 benefit recorded in
`tools/ppo_plan_v11/RESULTS.md`. Its registered hypothesis is that broader
on-policy exploration and a curriculum focused on controllable delays may
improve PPO's contribution. It assumes no ten-percent or publication outcome.
`PROTOCOL.md` fixes all budgets, cases, controls and promotion criteria before
new training or prospective evaluation.

The controller, causal forty-feature/eight-knot contract, physical limits,
50 ms service, strict 150 ms freshness limit, three-model checks, analytical
fallback and all reward mathematics are the frozen v11 implementation. The
training wrapper changes only case sampling. It does not grant PPO authority
on expired proposals or change longitudinal supervision.

Every seed starts from its exact original BC checkpoint. Initial log std -2.5
increases exploration while preserving the deterministic initial policy mean.
Actor Adam changes are damped by 0.1; the ordinary critic step is retained.
There are no extra imitation updates during the 65536 PPO transitions per
seed. All endpoints and 16384-step checkpoints are kept. Actual Adam step
counts and SB3 epoch counters are reported separately.

Training focuses on 0/50 ms delay, with broad declared state, road and traffic
parameters. The old random PPO generator already covered 50 ms; this study
does not claim otherwise. Removing 100 ms states from training avoids spending
actor-training samples where the strict proposal budget grants no authority.
Evaluation retains 0/50/100 ms cases in every whole-run average.

The new prospective namespace contains 72 fixtures, each tested with LQR,
adaptive/MPC, all three existing scalar PPOs, initial sequence BCs, corrected
v11 policies and new PPOs: 1008 six-second episodes. These are repeated policies
on 72 fixtures, not 1008 independent traffic scenarios. Confidence intervals
retain all seeds and mirror variants within 36 paired strata. V11's opened
cohort is diagnostic and never pooled into this new result.

`verify.py` replays every physical transition, complete analytical reward
shadow, causal feature, reward component, admitted three-model plan and
deterministic evaluation action. Seed-level audit caches pin input and source
hashes. The default command physically replays all transitions even when a
matching prior seed proof exists. The explicit `--reuse-training-audit` option
can resume an unchanged audit using matching seed proofs; its log identifies
every reuse. Changes to pinned sources invalidate them. A passing replay does
not imply the ten-percent performance and quality gates passed.

In a clean clone with recorded Python 3.10 dependencies, restore the v10 and
v11 evidence at the repository root before replaying this study. Archives can
also be reconstructed into an empty destination for inspection:

```bash
python -m tools.ppo_explore_v12.package --verify
python -m tools.ppo_explore_v12.package --restore /workspace/exploration-restored
```

For numerical replay with raw data at the clone's root:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m tools.ppo_explore_v12.verify
python -m pytest tools/ppo_plan_v11 tools/ppo_explore_v12 -q
```

Collectors refuse to overwrite existing scientific evidence. New studies run
`train` before `evaluate`; they need their own registered protocol and fresh
output location rather than reusing opened cases as confirmation. No actor or
checkpoint is selected from prospective outcomes. A changed shared controller
requires new matched evaluation. Native Webots transfer and actual runtime
deadline certification are separate work. No thesis drafts, figures or tables.
