# Factorial student anchor and proposal-credit pilot

The user authorized the next controlled experiment after revision9 PPO drift. [Reward audit](reward-audit.md) separates confirmed implementation behavior from causal hypotheses. [Protocol](protocol.json) freezes four arms (plain, anchor-only, credit-only, combined), three matched fresh RL seeds,100k transitions each:1.2million additional steps total. Every arm exactly inherits the same paired supervised student, fixed train-only preprocessing and a matched fresh critic/optimizer.

Anchor coefficient1 adds KL(frozen student||actor) on half current/half existing Step2 TRAIN-observation replay. No new labels. Credit predicts the effect of a **single current request**, compared with a zero request from identical current observer/worker/plant state, with zero future requests and zero future noise innovations. It preserves actual execution and masks ignored in-flight actions from actor/entropy gradients. This is privileged training-only model-predicted credit, not actual future outcome or a validated unbiased reward. The actor keeps exactly20 sensor/history features.

Freeze before training; choose checkpoints0/25k/50k/100k using2,052 DEV episodes. Publish selections before1,188 independent final episodes. Report all arms and endpoints. Step0 retention is not a PPO gain. No post-outcome coefficient/reward search, extra labels or training, gate edit or production promotion.

Use the pinned Python3.10 CPU research runtime (`/workspace/lans-venv/bin/python` here) and a new output directory. Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/workspace/lans-v10-numba MPLCONFIGDIR=/workspace/lans-setup/matplotlib`.

```bash
python integrations/webots/research/revision10/test_pilot.py -v
python integrations/webots/research/revision10/train10.py --output /tmp/lans-factorial/training
python integrations/webots/research/revision10/evaluate10.py --training /tmp/lans-factorial/training --output /tmp/lans-factorial/dev --split dev
python integrations/webots/research/revision10/evaluate10.py --training /tmp/lans-factorial/training --output /tmp/lans-factorial/evaluation --split evaluation --selection /tmp/lans-factorial/dev/selection.json
python integrations/webots/research/revision10/report10.py --run /tmp/lans-factorial
python integrations/webots/research/revision10/verify10.py --run /tmp/lans-factorial
```

Up to three single-thread subprocesses. Retain48 checkpoints/optimizer states, reward normalizers, all raw rows and representative input/action traces. Known tasks/fresh noise only; no native/generalization/MPC superiority claim. Equal RL-transition budget is not equal compute, because anchors and counterfactuals add overhead. Endpoint factorial contrasts are descriptive with three pairs. The credit factor combines reward and masking and cannot isolate those two subcomponents.

`anchor10.py` adapts the installed SB3 2.0.0 MIT-licensed `PPO.train`: only student KL and optional ignored-action masking change the learner. The zero-anchor/unmasked update is checked against stock SB3 on identical data/seeds within numerical tolerance. Frozen reference/replay arrays are reconstructed from versioned Step2 files on checkpoint load and excluded from checkpoint payloads; inference requires no teacher or truth input. `PPOAdapter` exposes the same normalized five-class residual mapping.
