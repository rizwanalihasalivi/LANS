# PPO-only contribution study

The new teacher-anchored actor improves the learned component's tracking effect
on the same fresh grid: **0.218080% lower RMSE than adaptive-only**, compared with
**0.012562%** for the old PPO actor. The incremental gain over the old actor is
**0.205544%**, with paired 95% interval [0.090215%, 0.408165%]. These are modest
absolute gains. They do not establish a large PPO-specific benefit or the 30%
target, and this candidate is not promoted as a completed framework.

This work is isolated on `research/ppo-benefit-v10`. Shared v8/v9 controller,
supervisor, guards and physical limits are unchanged. The other agent's safety,
progress and runtime work can be integrated separately after matched validation.
There is no thesis draft, research figure or presentation table in this study.

## Attribution and limitations

The initial BC actor already gains 0.216572% over adaptive-only. Anchored PPO's
gain over that actor is just 0.001511%, interval [-0.070394%, 0.072162%]. Against
continued BC with matched additional teacher updates, the anchored gain is
0.030768%, interval [-0.039759%, 0.114486%]. Both intervals include zero. The
evidence supports an improved trained actor relative to old PPO, but does not
establish substantial extra benefit from PPO fine-tuning beyond supervision.
Unregularized PPO gains 0.207695% over adaptive-only and 0.195158% over old PPO;
it is 0.008896% worse than initial BC, also without a conclusive difference.

Mean RMSE is 0.108608299 m for anchored PPO, 0.108845670 m for adaptive-only and
0.108831997 m for old PPO. LQR is 0.087289222 m. Thus the full anchored hybrid
is **24.4235% worse than LQR on this new cohort**; a component gain must not be
presented as overall LQR superiority. A common crossing failure occurs in case
52 for adaptive-only and all learned variants. All collide after 48 ticks; LQR
does not. This case has 100 ms actuation delay, so strict expiry excludes PPO.
The verifier checks that these delayed paths retain exactly the adaptive-only
commands. This is a shared controller failure, not proof of inevitability.

All three anchored actors fail the original failure/progress/heading gates.
Minimum LQR-relative progress is 29.8706%; mean heading RMS is 12.5541% higher
and steering-rate RMS 5.7016% higher. The 30% target and full promotion fail.
Original v8's earlier 5.186% result belongs to its separate cohort and remains
preserved. These fresh failure cases cannot be relabeled as untouched final data.
Confidence intervals are per-comparison finite-grid bootstrap summaries, not
simultaneous or universal guarantees. No native or actual-runtime benefit is
inferred from logical-time simulations or inference-worker unit tests.

## What changed and what was tested

New actors receive a versioned 30-feature observation including known queue,
delay, estimated dynamics and predicted next-application errors. Queries follow
the current command issue and retain original sensor timestamps. Logical service
is 50 ms; the 150 ms expiry bound is preserved. A causal teacher uses received
state, estimated dynamics and known commands, never true stiffness or future
NPC measurements. It scans 65 scalar corrections under the original robust
admission. Direct-teacher performance is retained as a separate analytical
reference, rather than credited to PPO.

The 64 training cases generate 7611 teacher transitions, including one failure.
Every old actor supplies its same-size initial network weights; new feature
columns start at zero. All three seeds receive 32 BC epochs, then 16384 actual
PPO steps. A second independently declared anchored arm starts again from each
BC endpoint and adds teacher-retention gradients during 16384 PPO steps per
seed. Total successful new PPO training is 98304 steps. Continued BC matches
the extra 1280 teacher updates per seed and adds zero PPO steps. Initial,
unregularized, anchored and continued-BC endpoints all remain saved.

There are 1296 prospective episodes: 864 original comparisons and 216 each for
anchored and continued BC. All use the same 72 declared scenario/speed/delay/
mirror fixtures, six-second whole-run failure penalties, and original gates.
Actor outcomes are averaged within fixture; 5000 bootstrap draws use 36 strata.
No actor/checkpoint selection or outcome-driven tuning is used. Training-only
forgetting diagnostics triggered the separately registered anchored arm; its
declaration precedes the original prospective assessment.

Two implementation failures and their data/source/logs are retained. The first
fails before optimization on an actor-width mismatch. The second saves 3072
interrupted transitions before the first PPO update, due to SB3's reserved
episode-info key. These are additional evidence, not successful PPO steps.
`ATTEMPTS.md` records the repairs. Raw replay checks physics, FIFO, rewards,
whole-run metrics, delayed actions, hashes and paired arithmetic. Continued-BC
weights reproduce exactly. PPO optimizer trajectories themselves are not rerun.

## Recovery and integration

`evidence/` stores complete raw data, policies/checkpoints, failed attempts,
source snapshots, protocols, diagnostics, audit and execution logs. Every bounded
ZIP, member and reconstructed large-file hash is checked; traces are never
sampled or shortened to fit GitHub. Restore into a fresh destination:

```bash
python -m tools.ppo_benefit_v10.package --verify
python -m tools.ppo_benefit_v10.package --restore /workspace/ppo-benefit-restored
```

For numerical replay, restore raw data at the cloned repository root and restore
the original policy dependency from
`tools/unified_campaign/evidence/python-v2-training.zip`. Use the recorded Python
3.10 dependencies and run `python -m tools.ppo_benefit_v10.verify`.
`ATTRIBUTION.json` is the technical result index under restored
`results/ppo-benefit-v10`; it distinguishes every training method and delay.

The new versioned loader and spawned worker reject legacy shape/contract/hash
errors and malformed replies. Read `INTEGRATION.md` before combining these models
with another controller repair. A changed supervisor or guard requires new
matched validation; no model is automatically promoted by this study.
