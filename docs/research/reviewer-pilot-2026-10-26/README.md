# Reviewer-driven archived PPO diagnostic

Completed 26 October 2026. This is Stage A of the reviewer-response plan, not a new causal PPO validation or final comparison.

90 fresh DEVELOPMENT episodes: 3 archived training seeds x 20 m/s x 2 known paths x 3 service conditions x 5 methods. Each method has 18 episodes. The six LQR/fixed noise replicates per condition are not additional independent training seeds. No training or checkpoint selection was performed.

| Method | Mean episode penalized lateral RMSE (m) | Reduction vs paired LQR | Survived |
|---|---:|---:|---:|
| lqr | 0.05373322 | 0.000% | 18/18 |
| fixed_m004 | 0.05279055 | 1.754% | 18/18 |
| fixed_p004 | 0.05298618 | 1.390% | 18/18 |
| scratch_100k | 0.05367659 | 0.105% | 18/18 |
| finetune_100k | 0.05171572 | 3.755% | 18/18 |

## Interpretation

The archived 100k fine-tuned residual PPO improves the aggregate lateral metric in this narrow diagnostic. This does not supersede earlier larger experiments, establish broad superiority, or demonstrate an incremental PPO gain over its supervised initialization: the initialization/student is not an arm in this screen. Scratch PPO provides little aggregate benefit. Fixed corrections remain important controls.

Per paired training/noise seed, fine-tuned PPO reduction versus LQR:
- Pair 0: 3.414% (descriptive, six episodes per method).
- Pair 1: 3.641% (descriptive, six episodes per method).
- Pair 2: 4.210% (descriptive, six episodes per method).

## Independent checks and limits

- Raw metrics recomputed for all 90 traces; steering amplitude/rate bounds checked.
- All 24 non-LQR 100 ms delayed cases exactly match paired LQR commands and plant trajectories. This is rejection/fallback, not learned compensation of 100 ms.
- Source and model hashes verified; 88 source/protocol snapshots retained.
- Independent metrics include steering-rate RMS, total steering movement and ESTIMATED heading RMSE. True heading error is not present in the historical trace and must be logged in the next runner.
- Archived policies use the historical pending/forecast input interface. They are not validated causal deployable policies. No zero-channel deployment promotion.
- Service delay is simulated; no OS deadline, independent-loop scheduling, native Webots or vehicle claim.
- Fresh noise on known paths is not unseen-path generalization. No reserved evaluation was accessed.
- Unchanged legacy gate uses 50 ms proposal-age rejection and blends a clipped full candidate. It is not a newly validated symbolic reasoner or the exact new unsaturated residual equation.
- Original manuscript 49x speedup, energy and global safety claims remain unsupported.
- First launch stopped before rollouts due to protocol-metadata validation; its log and failure description are preserved separately.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/lans-reviewer-mpl NUMBA_CACHE_DIR=/tmp/lans-reviewer-numba /workspace/lans-venv/bin/python tools/controller_review/reviewer_pilot.py --output /tmp/new-reviewer-pilot
python tools/controller_review/verify_reviewer_pilot.py --run /tmp/new-reviewer-pilot
```

Next: freeze the causal PPO interface and matched supervisor/gain ablation protocol before new training. No automatic full-budget training or final evaluation follows this diagnostic.
