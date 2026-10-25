# Step3: supervised actor → bounded PPO

Exact categorical five-logit initialization preserves the Step2 student, including its fixed train-only feature standardization. No Gaussian approximation, hidden-state actor input or gate change. Scratch PPO shares preprocessing, a fresh matched critic/optimizer and100k additional RL steps per seed. Three paired seeds make600k steps total; Step2 pretraining remains extra budget.

The [protocol](protocol.json) freezes checkpoints0/25k/50k/100k, independent development selection and fresh evaluation. Zero-step retention is explicitly allowed and is not a PPO improvement. Target KL limits each update relative to its rollout policy, not cumulative divergence from the student. No imitation replay, teacher loss or extra tuning follows observed outcomes.

Use the prepared Python3.10 CPU environment and a new output directory. Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/workspace/lans-v9-numba MPLCONFIGDIR=/workspace/lans-setup/matplotlib`.

```bash
python integrations/webots/research/revision9/test_step3.py -v
python integrations/webots/research/revision9/train9.py --output /tmp/lans-step3/training
python integrations/webots/research/revision9/evaluate9.py --training /tmp/lans-step3/training --output /tmp/lans-step3/dev --split dev
python integrations/webots/research/revision9/evaluate9.py --training /tmp/lans-step3/training --output /tmp/lans-step3/evaluation --split evaluation --selection /tmp/lans-step3/dev/selection.json
python integrations/webots/research/revision9/report9.py --run /tmp/lans-step3
python integrations/webots/research/revision9/verify9.py --run /tmp/lans-step3
```

Training uses at most two single-thread subprocesses; evaluation uses three. All checkpoints, optimizer states, reward normalizers, source snapshots, raw episode rows and representative traces are retained. Final comparison includes selected checkpoints and100k endpoints even when they regress. These are known task families with fresh noise; no native/generalization/MPC superiority claim is supported by this pilot alone.
