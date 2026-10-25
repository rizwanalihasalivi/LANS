# Step2: future-noise-independent teacher and sensor-only student

This bounded supervised experiment follows Step1's demonstrated finite-policy headroom. The teacher uses current true state/plant parameters, but **never the actual future sensor-noise stream**. The student uses exactly20 observed/history features and outputs one of five bounded residuals through the unchanged gate. No PPO fine-tuning or production deployment is included.

Training/data protocol freeze: `2e30f1a`. Closed-loop evaluator and success-screen freeze: `51d50f4`. [Protocol](protocol.json) gives all settings and stop rules. [Generated results](../../results/revision8-student/report.md) distinguish teacher performance, supervised prediction quality and actual student tracking.

## Teacher and data

For each of five held proposals, clone actual execution/observer/plant state and run200ms with independent zero/+Gaussian/−Gaussian future noise forecasts. Average those three costs. Choose the minimum, but abstain to zero if expected improvement over a zero proposal is ≤max(1e-7,0.1% of zero cost). This is a finite expected-cost approximation, not a global optimum or an unbiased full integration over noise.

Collect labels every5ticks when a worker submission is possible on zero, fixed−.04 and random-grid behavior trajectories. This covers more gate/history states than a single teacher trajectory. Train uses216 episodes; dev108. The noise repetitions and actual/forecast streams are separate; **no evaluation trajectory is used for labels or model selection**. No data is appended after observing outcomes.

The teacher still has privileged current hidden state/parameters and exact model/path information. A sensor-only student cannot be assumed to reproduce it. Future-noise dependence from Step1 is removed, but current partial-observation ambiguity remains a learnability limit.

## Supervised students

Three optimization seeds, fixed20epochs each,20→64→64→5 tanh classifier. Train-only feature standardization. Cross entropy plus normalized expected regret, with balanced zero/nonzero-label sampling. Checkpoint selected by DEV mean regret equally aggregated over episodes, earliest tie. All epochs remain in the logs. Class accuracy alone is insufficient; zero abstention makes it easy to achieve misleadingly high overall accuracy.

Student inference takes only20 finite observed channels. Teacher costs, truth, friction/stiffness and future draws are not inference arguments or features. Its `.pt` profile is a supervised classifier, not an SB3 PPO checkpoint; use `student.load(...).predict(...)`. The earlier native PPO worker is not silently repointed to these models.

## Evaluation and stop

540 fresh paired episodes compare LQR, fixed−.04, expected teacher, student and previous execution-trained PPO. Each of three fixed student/noise pairs covers three speeds, two known paths and six conditions. Previous PPO has different data and100k RL steps; it is a descriptive reference, not a matched supervised/RL training budget. Baselines share sensors, measured speed, gate, service delays and physical constraints.

The1% screen requires student gain over both LQR and fixed−.04 plus seed/region/survival conditions. Teacher performance does not count as student success. Stop after this report; no extra epochs, architecture search, data aggregation, gate changes or PPO fine-tuning follows the outcome automatically. No native or real-vehicle claim follows.

## Reproduction

Use the pinned Python3.10/CPU Torch2/SB3/Numba research runtime (`/workspace/lans-venv/bin/python` in this cloud instance). Outputs must be new.

```bash
cd /workspace/LANS
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/workspace/lans-v8-numba
export MPLCONFIGDIR=/workspace/lans-setup/matplotlib
python integrations/webots/research/revision8/test_step2.py -v
python integrations/webots/research/revision8/data.py --output /tmp/lans-step2/data
python integrations/webots/research/revision8/train_all.py --data /tmp/lans-step2/data --output /tmp/lans-step2/students
python integrations/webots/research/revision8/evaluate.py --students /tmp/lans-step2/students --output /tmp/lans-step2/evaluation
python integrations/webots/research/revision8/report.py --run /tmp/lans-step2
python integrations/webots/research/revision8/verify.py --run /tmp/lans-step2
```

Dataset generation/evaluation use three independent single-thread shards; student fitting uses at most two one-thread processes. Frozen source snapshots, complete label costs, episode groups, normalizations, selected weights, every epoch's metrics and all evaluation rows are retained. Forecast privilege tests, original-observation parity, split isolation and saved-model checks provide a reproducible audit trail.
